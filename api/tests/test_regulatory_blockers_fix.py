"""Tests for the 4 corrective blockers in PR #49 final gate.

Covers:
1. force_review_required forces REVIEW_REQUIRED from COMPLIANCE_READY/IN_REVIEW/DRAFT
2. compliance_blockers field (NOT prerequisites), dedup, resolution, NR-18
3. demo_classification (CONFIRMED_DEMO/UNKNOWN) replaces is_demo
4. plan_compliance_profile() dry-run/apply parity (CREATED/UPDATED/NO_CHANGE)
5. Readiness gate blocks on compliance_blockers regardless of status
6. Regulatory-only transaction persistence regression
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.core.utils import utc_now
from app.models.certificate import Certificate
from app.models.class_model import Class
from app.models.compliance import ComplianceStatus, CourseComplianceProfile, WorkloadSource
from app.models.course import Course, CourseModality, CourseType
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.student import Student
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User, UserRole
from app.scripts.import_wr_catalog import (
    BLOCKER_COURSE_FIELD_HISTORY_CONFLICT,
    BLOCKER_NR18_VARIANT_CONFIRMATION_REQUIRED,
    _build_blocker,
    _classify_enrollment_demo,
    _merge_blockers,
    plan_compliance_profile,
    reconcile_regulatory_compliance,
    run_regulatory_only,
)
from app.services.training_evidence_service import (
    RegulatoryCompletionState,
    evaluate_regulatory_state,
)

WR_TENANT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


def _make_manifest_entry(code: str, nr_family: str) -> dict:
    return {
        "code": code,
        "nr_family": nr_family,
        "name": f"Test {code}",
        "action": "CREATE",
        "content": {},
        "source_pdf": {"filename": "test.pdf", "sha256": "abc123", "pages": [1]},
    }


async def _cleanup_tenant(tenant_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Certificate).where(Certificate.tenant_id == tenant_id))
        await db.execute(delete(Enrollment).where(Enrollment.tenant_id == tenant_id))
        await db.execute(delete(Student).where(Student.tenant_id == tenant_id))
        await db.execute(delete(Class).where(Class.tenant_id == tenant_id))
        await db.execute(delete(CourseComplianceProfile).where(CourseComplianceProfile.tenant_id == tenant_id))
        await db.execute(delete(Course).where(Course.tenant_id == tenant_id))
        await db.execute(delete(User).where(User.tenant_id == tenant_id))
        await db.execute(delete(Tenant).where(Tenant.id == tenant_id))
        await db.commit()


async def _make_tenant(tenant_id: uuid.UUID, slug: str, name: str) -> None:
    async with AsyncSessionLocal() as db:
        tenant = Tenant(
            id=tenant_id,
            name=name,
            slug=slug,
            status=TenantStatus.ACTIVE,
            contact_name="Test",
            contact_email=f"{slug}@wr.com",
        )
        db.add(tenant)
        await db.commit()


async def _make_course(
    tenant_id: uuid.UUID,
    code: str,
    nr_family: str,
    carga_horaria: int,
    modality: CourseModality,
) -> Course:
    async with AsyncSessionLocal() as db:
        course = Course(
            tenant_id=tenant_id,
            code=code,
            name=f"Test {code}",
            category=f"NR {nr_family.split('-')[1]}",
            carga_horaria=carga_horaria,
            modality=modality,
            tipo_curso=CourseType.FORMACAO,
            price=100.0,
            is_active=True,
        )
        db.add(course)
        await db.commit()
        await db.refresh(course)
        return course


async def _get_course(tenant_id: uuid.UUID, code: str) -> Course:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Course).where(Course.tenant_id == tenant_id, Course.code == code)
        )
        return result.scalar_one()


async def _get_profile(tenant_id: uuid.UUID, code: str) -> CourseComplianceProfile | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CourseComplianceProfile)
            .join(Course, Course.id == CourseComplianceProfile.course_id)
            .where(CourseComplianceProfile.tenant_id == tenant_id, Course.code == code)
        )
        return result.scalar_one_or_none()


async def _make_enrollment_with_user(
    tenant_id: uuid.UUID,
    course_id: uuid.UUID,
    email: str = "admin-test@wr.com",
    cpf: str = "11122233344",
    class_location: str = "SP",
) -> uuid.UUID:
    """Create user+student+class+enrollment and return enrollment_id."""
    async with AsyncSessionLocal() as db:
        admin = User(
            tenant_id=tenant_id,
            email=email,
            full_name="Admin Test",
            role=UserRole.ADMIN,
            is_active=True,
            password_hash="x",
        )
        db.add(admin)
        await db.flush()

        student = Student(tenant_id=tenant_id, user_id=admin.id, cpf=cpf)
        db.add(student)
        await db.flush()

        cls = Class(
            tenant_id=tenant_id,
            course_id=course_id,
            responsible_admin_id=admin.id,
            start_date=utc_now().date(),
            end_date=utc_now().date(),
            max_students=20,
            location=class_location,
            status="ABERTA",
        )
        db.add(cls)
        await db.flush()

        enrollment = Enrollment(
            tenant_id=tenant_id,
            student_id=student.id,
            class_id=cls.id,
            price=100.0,
            status=EnrollmentStatus.CONFIRMADA,
        )
        db.add(enrollment)
        await db.commit()
        return enrollment.id


# ===========================================================================
# Test 1: COMPLIANCE_READY + force_review_required → REVIEW_REQUIRED
# ===========================================================================


@pytest.mark.asyncio
async def test_1_compliance_ready_forced_to_review_required():
    """A) profile COMPLIANCE_READY + Course SEMIPRESENCIAL + matrix PRESENCIAL
    + history present → Course doesn't change, profile.status = REVIEW_REQUIRED.
    """
    await _make_tenant(WR_TENANT_ID, "wr-b1a", "WR B1A")
    try:
        course = await _make_course(WR_TENANT_ID, "NR-33-AUT", "NR-33", 16, CourseModality.SEMIPRESENCIAL)
        await _make_enrollment_with_user(WR_TENANT_ID, course.id)

        # Pre-create a COMPLIANCE_READY profile
        async with AsyncSessionLocal() as db:
            profile = CourseComplianceProfile(
                tenant_id=WR_TENANT_ID,
                course_id=course.id,
                regulatory_standard="NR-33",
                regulatory_version="Trabalho em Espaço Confinado",
                delivery_mode="PRESENCIAL",
                workload_source=WorkloadSource.NORMATIVE_MINIMUM,
                workload_minutes=960,
                normative_minimum_minutes=960,
                requires_practical_component=True,
                requires_final_assessment=True,
                validity_period_months=12,
                certificate_required_fields=[],
                compliance_blockers=[],
                status=ComplianceStatus.COMPLIANCE_READY,
            )
            db.add(profile)
            await db.commit()

        manifest = {"courses": [_make_manifest_entry("NR-33-AUT", "NR-33")], "deactivate_codes": []}

        async with AsyncSessionLocal() as db:
            await run_regulatory_only(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        # Course NOT modified (history conflict)
        course_after = await _get_course(WR_TENANT_ID, "NR-33-AUT")
        assert course_after.modality == CourseModality.SEMIPRESENCIAL

        # Profile must be REVIEW_REQUIRED (forced from COMPLIANCE_READY)
        profile_after = await _get_profile(WR_TENANT_ID, "NR-33-AUT")
        assert profile_after.status == ComplianceStatus.REVIEW_REQUIRED
        blocker_codes = [b["code"] for b in profile_after.compliance_blockers]
        assert BLOCKER_COURSE_FIELD_HISTORY_CONFLICT in blocker_codes
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ===========================================================================
# Test 1B: IN_REVIEW → REVIEW_REQUIRED
# ===========================================================================


def test_1b_in_review_forced_to_review_required():
    """B) profile IN_REVIEW + force_review_required → REVIEW_REQUIRED."""
    course = MagicMock()
    course.carga_horaria = 16
    course.modality = CourseModality.SEMIPRESENCIAL

    existing = MagicMock()
    existing.status = ComplianceStatus.IN_REVIEW
    existing.compliance_blockers = []
    existing.regulatory_standard = "NR-33"
    existing.regulatory_version = "Trabalho em Espaço Confinado"
    existing.delivery_mode = "PRESENCIAL"
    existing.workload_source = WorkloadSource.NORMATIVE_MINIMUM
    existing.workload_minutes = 960
    existing.normative_minimum_minutes = 960
    existing.requires_practical_component = True
    existing.requires_final_assessment = True
    existing.validity_period_months = 12
    existing.prerequisites = None
    existing.certificate_required_fields = []

    entry = _make_manifest_entry("NR-33-AUT", "NR-33")
    plan = plan_compliance_profile(course, entry, existing, force_review_required=True)

    assert plan.target_status == ComplianceStatus.REVIEW_REQUIRED


# ===========================================================================
# Test 1C: DRAFT → REVIEW_REQUIRED
# ===========================================================================


def test_1c_draft_forced_to_review_required():
    """C) profile DRAFT + force_review_required → REVIEW_REQUIRED."""
    course = MagicMock()
    course.carga_horaria = 16
    course.modality = CourseModality.SEMIPRESENCIAL

    existing = MagicMock()
    existing.status = ComplianceStatus.DRAFT
    existing.compliance_blockers = []
    existing.regulatory_standard = "NR-33"
    existing.regulatory_version = "Trabalho em Espaço Confinado"
    existing.delivery_mode = "PRESENCIAL"
    existing.workload_source = WorkloadSource.NORMATIVE_MINIMUM
    existing.workload_minutes = 960
    existing.normative_minimum_minutes = 960
    existing.requires_practical_component = True
    existing.requires_final_assessment = True
    existing.validity_period_months = 12
    existing.prerequisites = None
    existing.certificate_required_fields = []

    entry = _make_manifest_entry("NR-33-AUT", "NR-33")
    plan = plan_compliance_profile(course, entry, existing, force_review_required=True)

    assert plan.target_status == ComplianceStatus.REVIEW_REQUIRED


# ===========================================================================
# Test 1D: ARCHIVED → stays ARCHIVED
# ===========================================================================


def test_1d_archived_stays_archived():
    """D) profile ARCHIVED + force_review_required → stays ARCHIVED."""
    course = MagicMock()
    course.carga_horaria = 16
    course.modality = CourseModality.SEMIPRESENCIAL

    existing = MagicMock()
    existing.status = ComplianceStatus.ARCHIVED
    existing.compliance_blockers = []
    existing.regulatory_standard = "NR-33"
    existing.regulatory_version = "Trabalho em Espaço Confinado"
    existing.delivery_mode = "PRESENCIAL"
    existing.workload_source = WorkloadSource.NORMATIVE_MINIMUM
    existing.workload_minutes = 960
    existing.normative_minimum_minutes = 960
    existing.requires_practical_component = True
    existing.requires_final_assessment = True
    existing.validity_period_months = 12
    existing.prerequisites = None
    existing.certificate_required_fields = []

    entry = _make_manifest_entry("NR-33-AUT", "NR-33")
    plan = plan_compliance_profile(course, entry, existing, force_review_required=True)

    assert plan.target_status == ComplianceStatus.ARCHIVED


# ===========================================================================
# Test 2: Blocker NOT in prerequisites
# ===========================================================================


@pytest.mark.asyncio
async def test_2_blocker_not_in_prerequisites():
    """3) COURSE_FIELD_HISTORY_CONFLICT must NOT appear in prerequisites."""
    await _make_tenant(WR_TENANT_ID, "wr-b2", "WR B2")
    try:
        course = await _make_course(WR_TENANT_ID, "NR-33-AUT", "NR-33", 16, CourseModality.SEMIPRESENCIAL)
        await _make_enrollment_with_user(WR_TENANT_ID, course.id)

        manifest = {"courses": [_make_manifest_entry("NR-33-AUT", "NR-33")], "deactivate_codes": []}

        async with AsyncSessionLocal() as db:
            await run_regulatory_only(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        profile = await _get_profile(WR_TENANT_ID, "NR-33-AUT")
        assert profile is not None

        # Blocker in compliance_blockers
        blocker_codes = [b["code"] for b in profile.compliance_blockers]
        assert BLOCKER_COURSE_FIELD_HISTORY_CONFLICT in blocker_codes

        # NOT in prerequisites
        if profile.prerequisites:
            assert BLOCKER_COURSE_FIELD_HISTORY_CONFLICT not in profile.prerequisites
            assert "[BLOCKER]" not in profile.prerequisites
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ===========================================================================
# Test 3: compliance_blockers dedup (10 runs → 1 blocker)
# ===========================================================================


def test_3_blocker_dedup():
    """4) Running _merge_blockers 10 times → only 1 COURSE_FIELD_HISTORY_CONFLICT."""
    blocker = _build_blocker(BLOCKER_COURSE_FIELD_HISTORY_CONFLICT, {"fields": ["modality"]})
    existing: list[dict] = []

    for _ in range(10):
        existing, _changes = _merge_blockers(existing, [blocker], set())

    conflict_blockers = [b for b in existing if b["code"] == BLOCKER_COURSE_FIELD_HISTORY_CONFLICT]
    assert len(conflict_blockers) == 1


# ===========================================================================
# Test 4: Blocker resolution without auto-promote
# ===========================================================================


def test_4_blocker_resolution_no_auto_promote():
    """5) When force_review_required=False, blocker is removed but status
    stays REVIEW_REQUIRED (no auto-promote to COMPLIANCE_READY).
    """
    course = MagicMock()
    course.carga_horaria = 40
    course.modality = CourseModality.PRESENCIAL

    existing = MagicMock()
    existing.status = ComplianceStatus.REVIEW_REQUIRED
    existing.compliance_blockers = [_build_blocker(BLOCKER_COURSE_FIELD_HISTORY_CONFLICT)]
    existing.regulatory_standard = "NR-33"
    existing.regulatory_version = "Trabalho em Espaço Confinado"
    existing.delivery_mode = "PRESENCIAL"
    existing.workload_source = WorkloadSource.NORMATIVE_MINIMUM
    existing.workload_minutes = 2400
    existing.normative_minimum_minutes = 2400
    existing.requires_practical_component = True
    existing.requires_final_assessment = True
    existing.validity_period_months = 12
    existing.prerequisites = None
    existing.certificate_required_fields = []

    entry = _make_manifest_entry("NR-33-SUP", "NR-33")
    # force_review_required=False → blocker should be removed
    plan = plan_compliance_profile(course, entry, existing, force_review_required=False)

    # Blocker removed
    blocker_codes = [b["code"] for b in plan.target_blockers]
    assert BLOCKER_COURSE_FIELD_HISTORY_CONFLICT not in blocker_codes

    # Status stays REVIEW_REQUIRED (no auto-promote)
    assert plan.target_status == ComplianceStatus.REVIEW_REQUIRED


# ===========================================================================
# Test 5: Enrollment without certificate → UNKNOWN (not NON_DEMO)
# ===========================================================================


def test_5_enrollment_no_cert_unknown():
    """6) Enrollment without certificate → UNKNOWN, not CONFIRMED_NON_DEMO."""
    classification, evidence = _classify_enrollment_demo(
        cert_nums=[],
        user_email="real@wr.com",
        class_location="SP",
    )
    assert classification == "UNKNOWN"
    assert evidence == []


# ===========================================================================
# Test 6: CONFIRMED_DEMO detection
# ===========================================================================


def test_6_confirmed_demo_detection():
    """7) Demo certificate prefix → CONFIRMED_DEMO with evidence."""
    classification, evidence = _classify_enrollment_demo(
        cert_nums=["DEMO-001"],
        user_email="real@wr.com",
        class_location="SP",
    )
    assert classification == "CONFIRMED_DEMO"
    assert "DEMO_CERTIFICATE_PREFIX" in evidence


def test_6b_confirmed_demo_email_domain():
    """7b) Demo email domain → CONFIRMED_DEMO with evidence."""
    classification, evidence = _classify_enrollment_demo(
        cert_nums=[],
        user_email="demo@wr.demo.local",
        class_location="SP",
    )
    assert classification == "CONFIRMED_DEMO"
    assert "DEMO_USER_EMAIL_DOMAIN" in evidence


def test_6c_confirmed_demo_class_location():
    """7c) Demo class location → CONFIRMED_DEMO with evidence."""
    classification, evidence = _classify_enrollment_demo(
        cert_nums=[],
        user_email="real@wr.com",
        class_location="DEMO-CERT-EAD",
    )
    assert classification == "CONFIRMED_DEMO"
    assert "DEMO_CLASS_LOCATION" in evidence


# ===========================================================================
# Test 7: UNKNOWN classification (fail-closed)
# ===========================================================================


def test_7_unknown_classification_fail_closed():
    """8) No demo evidence → UNKNOWN (never CONFIRMED_NON_DEMO)."""
    # Real-looking email, real class location, no demo cert
    classification, evidence = _classify_enrollment_demo(
        cert_nums=["CERT-001"],
        user_email="student@gmail.com",
        class_location="São Paulo",
    )
    assert classification == "UNKNOWN"
    assert evidence == []


# ===========================================================================
# Test 8: Dry-run missing profile → CREATED (no DB mutation)
# ===========================================================================


@pytest.mark.asyncio
async def test_8_dry_run_create_no_mutation():
    """9) Dry-run with missing profile → PROFILE_CREATED=1, DB has 0 profiles."""
    await _make_tenant(WR_TENANT_ID, "wr-b8", "WR B8")
    try:
        await _make_course(WR_TENANT_ID, "NR-33-SUP", "NR-33", 40, CourseModality.PRESENCIAL)
        manifest = {"courses": [_make_manifest_entry("NR-33-SUP", "NR-33")], "deactivate_codes": []}

        async with AsyncSessionLocal() as db:
            report = await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=True)
            await db.rollback()

        assert len(report["PROFILE_CREATED"]) == 1
        assert report["PROFILE_CREATED"][0]["code"] == "NR-33-SUP"

        # DB must have 0 profiles
        profile = await _get_profile(WR_TENANT_ID, "NR-33-SUP")
        assert profile is None
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ===========================================================================
# Test 9: Dry-run existing aligned → NO_CHANGE
# ===========================================================================


@pytest.mark.asyncio
async def test_9_dry_run_no_change_after_apply():
    """10) After apply, dry-run → PROFILE_NO_CHANGE=1, DB unchanged."""
    await _make_tenant(WR_TENANT_ID, "wr-b9", "WR B9")
    try:
        await _make_course(WR_TENANT_ID, "NR-33-SUP", "NR-33", 40, CourseModality.PRESENCIAL)
        manifest = {"courses": [_make_manifest_entry("NR-33-SUP", "NR-33")], "deactivate_codes": []}

        # Apply first
        async with AsyncSessionLocal() as db:
            await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        # Dry-run → NO_CHANGE
        async with AsyncSessionLocal() as db:
            report = await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=True)
            await db.rollback()

        assert len(report["PROFILE_NO_CHANGE"]) == 1
        assert len(report["PROFILE_CREATED"]) == 0
        assert len(report["PROFILE_UPDATED"]) == 0
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ===========================================================================
# Test 10: Dry-run existing divergent → UPDATED
# ===========================================================================


@pytest.mark.asyncio
async def test_10_dry_run_updated_divergent():
    """11) Profile with wrong delivery_mode → dry-run reports UPDATED with
    field/before/after. No DB mutation.
    """
    await _make_tenant(WR_TENANT_ID, "wr-b10", "WR B10")
    try:
        course = await _make_course(WR_TENANT_ID, "NR-33-SUP", "NR-33", 40, CourseModality.PRESENCIAL)

        # Pre-create profile with wrong delivery_mode
        async with AsyncSessionLocal() as db:
            profile = CourseComplianceProfile(
                tenant_id=WR_TENANT_ID,
                course_id=course.id,
                regulatory_standard="NR-33",
                regulatory_version="Trabalho em Espaço Confinado",
                delivery_mode="EAD",  # wrong — matrix says PRESENCIAL
                workload_source=WorkloadSource.NORMATIVE_MINIMUM,
                workload_minutes=2400,
                normative_minimum_minutes=2400,
                requires_practical_component=True,
                requires_final_assessment=True,
                validity_period_months=12,
                certificate_required_fields=[],
                compliance_blockers=[],
                status=ComplianceStatus.DRAFT,
            )
            db.add(profile)
            await db.commit()

        manifest = {"courses": [_make_manifest_entry("NR-33-SUP", "NR-33")], "deactivate_codes": []}

        # Dry-run → UPDATED
        async with AsyncSessionLocal() as db:
            report = await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=True)
            await db.rollback()

        assert len(report["PROFILE_UPDATED"]) == 1
        updated = report["PROFILE_UPDATED"][0]
        assert updated["code"] == "NR-33-SUP"
        # Must include changes with field/before/after
        assert "changes" in updated
        delivery_change = next(c for c in updated["changes"] if c["field"] == "delivery_mode")
        assert delivery_change["before"] == "EAD"
        assert delivery_change["after"] == "PRESENCIAL"

        # DB NOT mutated
        profile_after = await _get_profile(WR_TENANT_ID, "NR-33-SUP")
        assert profile_after.delivery_mode == "EAD"
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ===========================================================================
# Test 11: Dry-run does not mutate DB (status update)
# ===========================================================================


@pytest.mark.asyncio
async def test_11_dry_run_no_mutation_status_update():
    """12) Dry-run with COMPLIANCE_READY + history conflict → reports status
    change but does NOT mutate DB.
    """
    await _make_tenant(WR_TENANT_ID, "wr-b11", "WR B11")
    try:
        course = await _make_course(WR_TENANT_ID, "NR-33-AUT", "NR-33", 16, CourseModality.SEMIPRESENCIAL)
        await _make_enrollment_with_user(WR_TENANT_ID, course.id)

        # Pre-create COMPLIANCE_READY profile
        async with AsyncSessionLocal() as db:
            profile = CourseComplianceProfile(
                tenant_id=WR_TENANT_ID,
                course_id=course.id,
                regulatory_standard="NR-33",
                regulatory_version="Trabalho em Espaço Confinado",
                delivery_mode="PRESENCIAL",
                workload_source=WorkloadSource.NORMATIVE_MINIMUM,
                workload_minutes=960,
                normative_minimum_minutes=960,
                requires_practical_component=True,
                requires_final_assessment=True,
                validity_period_months=12,
                certificate_required_fields=[],
                compliance_blockers=[],
                status=ComplianceStatus.COMPLIANCE_READY,
            )
            db.add(profile)
            await db.commit()

        manifest = {"courses": [_make_manifest_entry("NR-33-AUT", "NR-33")], "deactivate_codes": []}

        # Dry-run
        async with AsyncSessionLocal() as db:
            report = await run_regulatory_only(db, WR_TENANT_ID, manifest, dry_run=True)
            await db.rollback()

        # Report must show UPDATED with status change
        assert len(report["PROFILE_UPDATED"]) == 1
        updated = report["PROFILE_UPDATED"][0]
        assert updated["status"] == ComplianceStatus.REVIEW_REQUIRED

        # DB NOT mutated — profile still COMPLIANCE_READY
        profile_after = await _get_profile(WR_TENANT_ID, "NR-33-AUT")
        assert profile_after.status == ComplianceStatus.COMPLIANCE_READY
        assert len(profile_after.compliance_blockers) == 0
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ===========================================================================
# Test 12: Apply uses same plan as dry-run (parity)
# ===========================================================================


@pytest.mark.asyncio
async def test_12_apply_dry_run_parity():
    """13) Apply and dry-run produce the same plan for the same input."""
    await _make_tenant(WR_TENANT_ID, "wr-b12", "WR B12")
    try:
        await _make_course(WR_TENANT_ID, "NR-33-SUP", "NR-33", 16, CourseModality.SEMIPRESENCIAL)
        manifest = {"courses": [_make_manifest_entry("NR-33-SUP", "NR-33")], "deactivate_codes": []}

        # Dry-run plan
        async with AsyncSessionLocal() as db:
            dry_report = await run_regulatory_only(db, WR_TENANT_ID, manifest, dry_run=True)
            await db.rollback()

        # Apply plan
        async with AsyncSessionLocal() as db:
            apply_report = await run_regulatory_only(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        # Both must report the same actions
        assert len(dry_report["PROFILE_CREATED"]) == len(apply_report["PROFILE_CREATED"])
        assert len(dry_report["PROFILE_UPDATED"]) == len(apply_report["PROFILE_UPDATED"])
        assert len(dry_report["PROFILE_NO_CHANGE"]) == len(apply_report["PROFILE_NO_CHANGE"])

        # Same status target
        dry_status = dry_report["PROFILE_CREATED"][0]["status"]
        apply_status = apply_report["PROFILE_CREATED"][0]["status"]
        assert dry_status == apply_status
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ===========================================================================
# Test 13: Readiness blocks on compliance_blockers (regardless of status)
# ===========================================================================


@pytest.mark.asyncio
async def test_13_readiness_blocks_on_blockers():
    """14) status=COMPLIANCE_READY + blockers=[COURSE_FIELD_HISTORY_CONFLICT]
    → BLOCKED.
    """
    await _make_tenant(WR_TENANT_ID, "wr-b13", "WR B13")
    try:
        course = await _make_course(WR_TENANT_ID, "NR-33-AUT", "NR-33", 16, CourseModality.PRESENCIAL)
        enrollment_id = await _make_enrollment_with_user(WR_TENANT_ID, course.id)

        # Create profile with COMPLIANCE_READY but WITH a blocker
        async with AsyncSessionLocal() as db:
            profile = CourseComplianceProfile(
                tenant_id=WR_TENANT_ID,
                course_id=course.id,
                regulatory_standard="NR-33",
                regulatory_version="Trabalho em Espaço Confinado",
                delivery_mode="PRESENCIAL",
                workload_source=WorkloadSource.NORMATIVE_MINIMUM,
                workload_minutes=960,
                normative_minimum_minutes=960,
                requires_practical_component=True,
                requires_final_assessment=True,
                validity_period_months=12,
                certificate_required_fields=[],
                compliance_blockers=[_build_blocker(BLOCKER_COURSE_FIELD_HISTORY_CONFLICT)],
                status=ComplianceStatus.COMPLIANCE_READY,
            )
            db.add(profile)
            await db.commit()

        async with AsyncSessionLocal() as db:
            evaluation = await evaluate_regulatory_state(
                db, tenant_id=WR_TENANT_ID, enrollment_id=enrollment_id, persist=False,
            )

        assert evaluation.state == RegulatoryCompletionState.COMPLIANCE_REVIEW_REQUIRED
        assert any("COURSE_FIELD_HISTORY_CONFLICT" in b for b in evaluation.blockers)
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ===========================================================================
# Test 14: Readiness blocks on divergence (no blockers, status READY)
# ===========================================================================


@pytest.mark.asyncio
async def test_14_readiness_blocks_on_divergence():
    """14B) status=COMPLIANCE_READY + blockers=[] + Course/Profile divergent
    → BLOCKED.
    """
    await _make_tenant(WR_TENANT_ID, "wr-b14", "WR B14")
    try:
        # Course=SEMIPRESENCIAL, Profile=PRESENCIAL → divergence
        course = await _make_course(WR_TENANT_ID, "NR-33-AUT", "NR-33", 16, CourseModality.SEMIPRESENCIAL)
        enrollment_id = await _make_enrollment_with_user(WR_TENANT_ID, course.id)

        async with AsyncSessionLocal() as db:
            profile = CourseComplianceProfile(
                tenant_id=WR_TENANT_ID,
                course_id=course.id,
                regulatory_standard="NR-33",
                regulatory_version="Trabalho em Espaço Confinado",
                delivery_mode="PRESENCIAL",
                workload_source=WorkloadSource.NORMATIVE_MINIMUM,
                workload_minutes=960,
                normative_minimum_minutes=960,
                requires_practical_component=True,
                requires_final_assessment=True,
                validity_period_months=12,
                certificate_required_fields=[],
                compliance_blockers=[],
                status=ComplianceStatus.COMPLIANCE_READY,
            )
            db.add(profile)
            await db.commit()

        async with AsyncSessionLocal() as db:
            evaluation = await evaluate_regulatory_state(
                db, tenant_id=WR_TENANT_ID, enrollment_id=enrollment_id, persist=False,
            )

        assert evaluation.state == RegulatoryCompletionState.COMPLIANCE_REVIEW_REQUIRED
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ===========================================================================
# Test 15: Fresh migration (compliance_blockers exists, JSONB, NOT NULL, default [])
# ===========================================================================


@pytest.mark.asyncio
async def test_15_fresh_migration_compliance_blockers():
    """15) Fresh migration: compliance_blockers column exists with correct
    type, NOT NULL, default [].
    """
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        result = await db.execute(text(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_name = 'course_compliance_profiles' "
            "AND column_name = 'compliance_blockers'"
        ))
        row = result.first()
        assert row is not None, "compliance_blockers column must exist"
        assert row.data_type == "jsonb", f"Expected jsonb, got {row.data_type}"
        assert row.is_nullable == "NO", "compliance_blockers must be NOT NULL"
        assert "'[]'::jsonb" in (row.column_default or ""), \
            f"Expected default '[]'::jsonb, got {row.column_default}"


# ===========================================================================
# Test 16: Regulatory-only persistence regression (commit on apply)
# ===========================================================================


@pytest.mark.asyncio
async def test_16_regulatory_only_persistence_regression():
    """20) --regulatory-only --apply persists (commit), --dry-run rolls back.
    Exception rolls back.
    """
    await _make_tenant(WR_TENANT_ID, "wr-b16", "WR B16")
    try:
        await _make_course(WR_TENANT_ID, "NR-33-SUP", "NR-33", 16, CourseModality.SEMIPRESENCIAL)
        manifest = {"courses": [_make_manifest_entry("NR-33-SUP", "NR-33")], "deactivate_codes": []}

        # Apply persists
        async with AsyncSessionLocal() as db:
            await run_regulatory_only(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        course = await _get_course(WR_TENANT_ID, "NR-33-SUP")
        assert course.carga_horaria == 40
        profile = await _get_profile(WR_TENANT_ID, "NR-33-SUP")
        assert profile is not None

        # Exception rolls back
        await _cleanup_tenant(WR_TENANT_ID)
        await _make_tenant(WR_TENANT_ID, "wr-b16b", "WR B16B")
        await _make_course(WR_TENANT_ID, "NR-33-SUP", "NR-33", 16, CourseModality.SEMIPRESENCIAL)

        async with AsyncSessionLocal() as db:
            try:
                await run_regulatory_only(db, WR_TENANT_ID, manifest, dry_run=False)
                raise RuntimeError("Simulated failure")
            except RuntimeError:
                await db.rollback()

        course_after = await _get_course(WR_TENANT_ID, "NR-33-SUP")
        assert course_after.carga_horaria == 16, "Rollback must restore carga_horaria"
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ===========================================================================
# Test 17: NR-18-F has NR18_VARIANT_CONFIRMATION_REQUIRED blocker
# ===========================================================================


@pytest.mark.asyncio
async def test_17_nr18_variant_blocker():
    """NR-18-F profile must have NR18_VARIANT_CONFIRMATION_REQUIRED blocker."""
    await _make_tenant(WR_TENANT_ID, "wr-b17", "WR B17")
    try:
        await _make_course(WR_TENANT_ID, "NR-18-F", "NR-18", 4, CourseModality.EAD)
        manifest = {"courses": [_make_manifest_entry("NR-18-F", "NR-18")], "deactivate_codes": []}

        async with AsyncSessionLocal() as db:
            await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        profile = await _get_profile(WR_TENANT_ID, "NR-18-F")
        assert profile is not None
        assert profile.status == ComplianceStatus.REVIEW_REQUIRED
        blocker_codes = [b["code"] for b in profile.compliance_blockers]
        assert BLOCKER_NR18_VARIANT_CONFIRMATION_REQUIRED in blocker_codes
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ===========================================================================
# Test 18: Profile report includes changes for UPDATED
# ===========================================================================


@pytest.mark.asyncio
async def test_18_profile_report_updated_includes_changes():
    """Profile report UPDATED must include code + changes with field/before/after."""
    await _make_tenant(WR_TENANT_ID, "wr-b18", "WR B18")
    try:
        course = await _make_course(WR_TENANT_ID, "NR-33-SUP", "NR-33", 40, CourseModality.PRESENCIAL)

        # Pre-create profile with wrong delivery_mode
        async with AsyncSessionLocal() as db:
            profile = CourseComplianceProfile(
                tenant_id=WR_TENANT_ID,
                course_id=course.id,
                regulatory_standard="NR-33",
                regulatory_version="Trabalho em Espaço Confinado",
                delivery_mode="EAD",
                workload_source=WorkloadSource.NORMATIVE_MINIMUM,
                workload_minutes=2400,
                normative_minimum_minutes=2400,
                requires_practical_component=True,
                requires_final_assessment=True,
                validity_period_months=12,
                certificate_required_fields=[],
                compliance_blockers=[],
                status=ComplianceStatus.DRAFT,
            )
            db.add(profile)
            await db.commit()

        manifest = {"courses": [_make_manifest_entry("NR-33-SUP", "NR-33")], "deactivate_codes": []}

        async with AsyncSessionLocal() as db:
            report = await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        assert len(report["PROFILE_UPDATED"]) == 1
        updated = report["PROFILE_UPDATED"][0]
        assert updated["code"] == "NR-33-SUP"
        assert "changes" in updated
        delivery_change = next(c for c in updated["changes"] if c["field"] == "delivery_mode")
        assert delivery_change["before"] == "EAD"
        assert delivery_change["after"] == "PRESENCIAL"
    finally:
        await _cleanup_tenant(WR_TENANT_ID)
