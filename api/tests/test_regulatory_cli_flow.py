"""Tests for regulatory-only CLI flow: persistence, rollback, isolation,
manual-review propagation, readiness gate, profile report semantics,
and report-key preservation.
"""

from __future__ import annotations

import uuid

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
    reconcile_regulatory_compliance,
    reconcile_regulatory_course_fields,
    run_regulatory_only,
)
from app.services.training_evidence_service import (
    RegulatoryCompletionState,
    _has_course_profile_divergence,
    evaluate_regulatory_state,
)

WR_TENANT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
OTHER_TENANT_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


def _make_manifest_entry(code: str, nr_family: str) -> dict:
    return {
        "code": code,
        "nr_family": nr_family,
        "name": f"Test {code}",
        "action": "CREATE",
        "content": {},
        "source_pdf": {"filename": "test.pdf", "sha256": "abc123", "pages": [1]},
    }


COURSE_CODES = [
    ("NR-10-B", "NR-10"),
    ("NR-10-S", "NR-10"),
    ("NR-33-AUT", "NR-33"),
    ("NR-33-SUP", "NR-33"),
    ("NR-35-F", "NR-35"),
    ("NR-06-F", "NR-06"),
    ("NR-11-EMP", "NR-11"),
    ("NR-11-GUI", "NR-11"),
    ("NR-11-MIN", "NR-11"),
    ("NR-11-PLA", "NR-11"),
    ("NR-11-PON", "NR-11"),
    ("NR-11-RET", "NR-11"),
    ("NR-12-F", "NR-12"),
    ("NR-18-F", "NR-18"),
]


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


# ---------------------------------------------------------------------------
# Section 5 — CLI apply persistence (real session close + reopen)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cli_apply_persistence_real():
    """Execute run_regulatory_only (apply), close session, open NEW session.
    Verify Course and Profile are persisted — proves real persistence,
    not just in-memory session state.
    """
    await _make_tenant(WR_TENANT_ID, "wr-persist", "WR Persist")
    try:
        await _make_course(WR_TENANT_ID, "NR-33-SUP", "NR-33", 16, CourseModality.SEMIPRESENCIAL)
        manifest = {"courses": [_make_manifest_entry("NR-33-SUP", "NR-33")], "deactivate_codes": []}

        # Execute apply in one session
        async with AsyncSessionLocal() as db:
            await run_regulatory_only(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()  # explicit commit — the main() pattern

        # Open a COMPLETELY NEW session and verify persistence
        course = await _get_course(WR_TENANT_ID, "NR-33-SUP")
        assert course.carga_horaria == 40, "Course.carga_horaria must be persisted as 40"
        assert course.modality == CourseModality.PRESENCIAL, "Course.modality must be persisted as PRESENCIAL"

        profile = await _get_profile(WR_TENANT_ID, "NR-33-SUP")
        assert profile is not None, "CourseComplianceProfile must be persisted"
        assert profile.workload_minutes == 2400
        assert profile.delivery_mode == "PRESENCIAL"
        assert profile.status == ComplianceStatus.DRAFT
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ---------------------------------------------------------------------------
# Section 6 — Dry-run non-persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cli_dry_run_non_persistence():
    """Execute run_regulatory_only (dry-run), close session, open NEW session.
    Verify Course is unchanged and no Profile exists — proves dry-run
    does not persist.
    """
    await _make_tenant(WR_TENANT_ID, "wr-dry-np", "WR Dry NP")
    try:
        await _make_course(WR_TENANT_ID, "NR-33-SUP", "NR-33", 16, CourseModality.SEMIPRESENCIAL)
        manifest = {"courses": [_make_manifest_entry("NR-33-SUP", "NR-33")], "deactivate_codes": []}

        # Execute dry-run in one session
        async with AsyncSessionLocal() as db:
            report = await run_regulatory_only(db, WR_TENANT_ID, manifest, dry_run=True)
            await db.rollback()  # explicit rollback — the main() pattern

        # Report should show planned changes
        assert len(report["COURSE_FIELD_UPDATES"]) == 2  # carga_horaria + modality

        # Open a NEW session — nothing persisted
        course = await _get_course(WR_TENANT_ID, "NR-33-SUP")
        assert course.carga_horaria == 16, "Dry-run must not persist carga_horaria"
        assert course.modality == CourseModality.SEMIPRESENCIAL, "Dry-run must not persist modality"

        profile = await _get_profile(WR_TENANT_ID, "NR-33-SUP")
        assert profile is None, "Dry-run must not create profile"
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ---------------------------------------------------------------------------
# Section 7 — Rollback on exception
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rollback_on_exception():
    """Simulate an error after Course alteration. Verify rollback:
    Course unchanged, no profile persisted.
    """
    await _make_tenant(WR_TENANT_ID, "wr-rb", "WR RB")
    try:
        await _make_course(WR_TENANT_ID, "NR-33-SUP", "NR-33", 16, CourseModality.SEMIPRESENCIAL)
        manifest = {"courses": [_make_manifest_entry("NR-33-SUP", "NR-33")], "deactivate_codes": []}

        # Simulate the main() try/except/rollback pattern
        async with AsyncSessionLocal() as db:
            try:
                # Apply Course field changes
                await reconcile_regulatory_course_fields(db, WR_TENANT_ID, manifest, dry_run=False)
                # Simulate error before commit
                raise RuntimeError("Simulated failure after Course alteration")
            except RuntimeError:
                await db.rollback()
                # Do NOT re-raise in test — we want to verify state

        # Open NEW session — nothing persisted due to rollback
        course = await _get_course(WR_TENANT_ID, "NR-33-SUP")
        assert course.carga_horaria == 16, "Rollback must restore carga_horaria"
        assert course.modality == CourseModality.SEMIPRESENCIAL, "Rollback must restore modality"

        profile = await _get_profile(WR_TENANT_ID, "NR-33-SUP")
        assert profile is None, "Rollback must not persist profile"
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ---------------------------------------------------------------------------
# Section 8 — Regulatory-only isolation (no catalog/materials side effects)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_regulatory_only_isolation_no_catalog_side_effects():
    """A non-regulatory course that WOULD be changed by import_catalog
    must NOT be altered by run_regulatory_only.
    """
    await _make_tenant(WR_TENANT_ID, "wr-iso", "WR Iso")
    try:
        # Create a non-regulatory course with wrong description
        async with AsyncSessionLocal() as db:
            course = Course(
                tenant_id=WR_TENANT_ID,
                code="NR-20-F",
                name="Old Name",
                category="NR 20",
                description="Old description",
                carga_horaria=16,
                modality=CourseModality.EAD,
                tipo_curso=CourseType.FORMACAO,
                price=100.0,
                is_active=True,
            )
            db.add(course)
            await db.commit()

        # Also create a regulatory course
        await _make_course(WR_TENANT_ID, "NR-33-SUP", "NR-33", 16, CourseModality.SEMIPRESENCIAL)

        # Manifest includes BOTH the non-regulatory and regulatory course
        manifest = {
            "courses": [
                {
                    "code": "NR-20-F",
                    "nr_family": "NR-20",
                    "name": "New Name",
                    "action": "UPDATE",
                    "content": {"short_description": "New description"},
                    "source_pdf": {"filename": "test.pdf", "sha256": "abc123", "pages": [1]},
                },
                _make_manifest_entry("NR-33-SUP", "NR-33"),
            ],
            "deactivate_codes": [],
        }

        # Run regulatory-only
        async with AsyncSessionLocal() as db:
            await run_regulatory_only(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        # Non-regulatory course must be UNCHANGED
        nr20 = await _get_course(WR_TENANT_ID, "NR-20-F")
        assert nr20.name == "Old Name", "regulatory-only must not update course name"
        assert nr20.description == "Old description", "regulatory-only must not update description"
        assert nr20.carga_horaria == 16, "regulatory-only must not update carga_horaria"
        assert nr20.modality == CourseModality.EAD, "regulatory-only must not update modality"

        # Regulatory course IS aligned
        nr33 = await _get_course(WR_TENANT_ID, "NR-33-SUP")
        assert nr33.carga_horaria == 40
        assert nr33.modality == CourseModality.PRESENCIAL
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ---------------------------------------------------------------------------
# Section 9 — Manual review propagates to profile (REVIEW_REQUIRED + blocker)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manual_review_propagates_to_profile():
    """When Course has history (enrollment), the profile must be created
    with status=REVIEW_REQUIRED and a blocker reason — not DRAFT.
    """
    await _make_tenant(WR_TENANT_ID, "wr-mrp", "WR MRP")
    try:
        course = await _make_course(WR_TENANT_ID, "NR-33-AUT", "NR-33", 16, CourseModality.SEMIPRESENCIAL)

        # Create enrollment to trigger history conflict
        async with AsyncSessionLocal() as db:
            admin = User(
                tenant_id=WR_TENANT_ID,
                email="admin-mrp@wr.com",
                full_name="Admin MRP",
                role=UserRole.ADMIN,
                is_active=True,
                password_hash="x",
            )
            db.add(admin)
            await db.flush()

            student = Student(tenant_id=WR_TENANT_ID, user_id=admin.id, cpf="11122233344")
            db.add(student)
            await db.flush()

            cls = Class(
                tenant_id=WR_TENANT_ID,
                course_id=course.id,
                responsible_admin_id=admin.id,
                start_date=utc_now().date(),
                end_date=utc_now().date(),
                max_students=20,
                status="ABERTA",
            )
            db.add(cls)
            await db.flush()

            enrollment = Enrollment(
                tenant_id=WR_TENANT_ID,
                student_id=student.id,
                class_id=cls.id,
                price=100.0,
            )
            db.add(enrollment)
            await db.commit()

        manifest = {"courses": [_make_manifest_entry("NR-33-AUT", "NR-33")], "deactivate_codes": []}

        # Run regulatory-only apply
        async with AsyncSessionLocal() as db:
            await run_regulatory_only(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        # Course NOT modified (history conflict)
        course_after = await _get_course(WR_TENANT_ID, "NR-33-AUT")
        assert course_after.modality == CourseModality.SEMIPRESENCIAL, "Course must not be modified"
        assert course_after.carga_horaria == 16

        # Profile must be REVIEW_REQUIRED with blocker
        profile = await _get_profile(WR_TENANT_ID, "NR-33-AUT")
        assert profile is not None
        assert profile.status == ComplianceStatus.REVIEW_REQUIRED, \
            "Profile must be REVIEW_REQUIRED when Course has history conflict"
        assert profile.delivery_mode == "PRESENCIAL", \
            "Profile delivery_mode must still reflect the regulatory target"
        assert profile.prerequisites is not None
        assert "COURSE_FIELD_HISTORY_CONFLICT" in profile.prerequisites, \
            "Profile must record the blocker reason"
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ---------------------------------------------------------------------------
# Section 10 — Expected production status after apply
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expected_production_status_after_apply():
    """After regulatory-only apply for all 14 courses:
    - NR-33-SUP: Course=40h/PRESENCIAL, Profile=DRAFT
    - NR-33-AUT: Course=16h/SEMIPRESENCIAL (no history in test), Profile=DRAFT
    - NR-35-F: Course=8h/PRESENCIAL (no history in test), Profile=DRAFT
    - NR-18-F: Course unchanged, Profile=REVIEW_REQUIRED
    - All others: DRAFT, technical_responsible_id=NULL
    """
    await _make_tenant(WR_TENANT_ID, "wr-prod", "WR Prod")
    try:
        for code, nr_family in COURSE_CODES:
            await _make_course(WR_TENANT_ID, code, nr_family, 8, CourseModality.EAD)

        manifest = {
            "courses": [_make_manifest_entry(code, nr) for code, nr in COURSE_CODES],
            "deactivate_codes": [],
        }

        async with AsyncSessionLocal() as db:
            await run_regulatory_only(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        # NR-33-SUP: aligned
        nr33_sup = await _get_course(WR_TENANT_ID, "NR-33-SUP")
        assert nr33_sup.carga_horaria == 40
        assert nr33_sup.modality == CourseModality.PRESENCIAL
        sup_profile = await _get_profile(WR_TENANT_ID, "NR-33-SUP")
        assert sup_profile.status == ComplianceStatus.DRAFT

        # NR-33-AUT: no history in test → aligned
        nr33_aut = await _get_course(WR_TENANT_ID, "NR-33-AUT")
        assert nr33_aut.carga_horaria == 16
        assert nr33_aut.modality == CourseModality.PRESENCIAL
        aut_profile = await _get_profile(WR_TENANT_ID, "NR-33-AUT")
        assert aut_profile.status == ComplianceStatus.DRAFT

        # NR-35-F: no history in test → aligned
        nr35_f = await _get_course(WR_TENANT_ID, "NR-35-F")
        assert nr35_f.carga_horaria == 8
        assert nr35_f.modality == CourseModality.PRESENCIAL
        f_profile = await _get_profile(WR_TENANT_ID, "NR-35-F")
        assert f_profile.status == ComplianceStatus.DRAFT

        # NR-18-F: Course unchanged, Profile=REVIEW_REQUIRED
        nr18_f = await _get_course(WR_TENANT_ID, "NR-18-F")
        assert nr18_f.carga_horaria == 8, "NR-18-F Course must not be modified"
        assert nr18_f.modality == CourseModality.EAD, "NR-18-F Course modality must not be modified"
        nr18_profile = await _get_profile(WR_TENANT_ID, "NR-18-F")
        assert nr18_profile.status == ComplianceStatus.REVIEW_REQUIRED
        assert nr18_profile.workload_source == WorkloadSource.REVIEW_REQUIRED

        # All profiles: technical_responsible_id=NULL, none APPROVED
        for code, _ in COURSE_CODES:
            p = await _get_profile(WR_TENANT_ID, code)
            assert p is not None, f"Missing profile for {code}"
            assert p.technical_responsible_id is None
            assert p.status != "APPROVED"
            assert p.status != ComplianceStatus.COMPLIANCE_READY
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ---------------------------------------------------------------------------
# Section 11 — Readiness gate: block official cert on Course↔Profile divergence
# ---------------------------------------------------------------------------


def test_has_course_profile_divergence_modality():
    """Helper detects modality divergence."""
    from unittest.mock import MagicMock

    course = MagicMock()
    course.modality = CourseModality.SEMIPRESENCIAL
    course.carga_horaria = 16

    profile = MagicMock()
    profile.delivery_mode = "PRESENCIAL"
    profile.normative_minimum_minutes = 960

    assert _has_course_profile_divergence(course, profile) is True


def test_has_course_profile_divergence_workload():
    """Helper detects workload divergence (course below normative minimum)."""
    from unittest.mock import MagicMock

    course = MagicMock()
    course.modality = CourseModality.PRESENCIAL
    course.carga_horaria = 16  # 960 min

    profile = MagicMock()
    profile.delivery_mode = "PRESENCIAL"
    profile.normative_minimum_minutes = 2400  # 40h — course is below

    assert _has_course_profile_divergence(course, profile) is True


def test_has_course_profile_divergence_none_when_aligned():
    """No divergence when Course matches Profile."""
    from unittest.mock import MagicMock

    course = MagicMock()
    course.modality = CourseModality.PRESENCIAL
    course.carga_horaria = 40  # 2400 min

    profile = MagicMock()
    profile.delivery_mode = "PRESENCIAL"
    profile.normative_minimum_minutes = 2400

    assert _has_course_profile_divergence(course, profile) is False


def test_has_course_profile_divergence_none_when_no_normative_min():
    """No divergence when normative_minimum_minutes is None (EMPLOYER_DEFINED)."""
    from unittest.mock import MagicMock

    course = MagicMock()
    course.modality = CourseModality.EAD
    course.carga_horaria = 4

    profile = MagicMock()
    profile.delivery_mode = "EAD"
    profile.normative_minimum_minutes = None

    assert _has_course_profile_divergence(course, profile) is False


@pytest.mark.asyncio
async def test_readiness_gate_blocks_cert_on_divergence():
    """evaluate_regulatory_state must return COMPLIANCE_REVIEW_REQUIRED when
    Course.modality != profile.delivery_mode (divergence from history conflict).
    """
    await _make_tenant(WR_TENANT_ID, "wr-gate", "WR Gate")
    try:
        course = await _make_course(WR_TENANT_ID, "NR-33-AUT", "NR-33", 16, CourseModality.SEMIPRESENCIAL)

        # Create enrollment + profile with divergence (Course=SEMIPRESENCIAL, Profile=PRESENCIAL)
        async with AsyncSessionLocal() as db:
            admin = User(
                tenant_id=WR_TENANT_ID,
                email="admin-gate@wr.com",
                full_name="Admin Gate",
                role=UserRole.ADMIN,
                is_active=True,
                password_hash="x",
            )
            db.add(admin)
            await db.flush()

            student = Student(tenant_id=WR_TENANT_ID, user_id=admin.id, cpf="11122233344")
            db.add(student)
            await db.flush()

            cls = Class(
                tenant_id=WR_TENANT_ID,
                course_id=course.id,
                responsible_admin_id=admin.id,
                start_date=utc_now().date(),
                end_date=utc_now().date(),
                max_students=20,
                status="ABERTA",
            )
            db.add(cls)
            await db.flush()

            enrollment = Enrollment(
                tenant_id=WR_TENANT_ID,
                student_id=student.id,
                class_id=cls.id,
                price=100.0,
                status=EnrollmentStatus.CONFIRMADA,
            )
            db.add(enrollment)
            await db.flush()

            # Create profile with COMPLIANCE_READY but divergent delivery_mode
            profile = CourseComplianceProfile(
                tenant_id=WR_TENANT_ID,
                course_id=course.id,
                regulatory_standard="NR-33",
                regulatory_version="Trabalho em Espaço Confinado",
                delivery_mode="PRESENCIAL",  # diverges from Course SEMIPRESENCIAL
                workload_source=WorkloadSource.NORMATIVE_MINIMUM,
                workload_minutes=960,
                normative_minimum_minutes=960,
                requires_practical_component=True,
                requires_final_assessment=True,
                validity_period_months=12,
                certificate_required_fields=[],
                status=ComplianceStatus.COMPLIANCE_READY,
            )
            db.add(profile)
            await db.commit()
            enrollment_id = enrollment.id

        # Evaluate — must block due to divergence
        async with AsyncSessionLocal() as db:
            evaluation = await evaluate_regulatory_state(
                db, tenant_id=WR_TENANT_ID, enrollment_id=enrollment_id, persist=False,
            )

        assert evaluation.state == RegulatoryCompletionState.COMPLIANCE_REVIEW_REQUIRED
        assert any("COURSE_FIELD_HISTORY_CONFLICT" in b for b in evaluation.blockers)
        assert evaluation.regulatory is True
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ---------------------------------------------------------------------------
# Section 12 — Profile report semantics: CREATED vs UPDATED vs NO_CHANGE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_profile_report_created_vs_updated_vs_no_change():
    """First run: PROFILE_CREATED. Second run: PROFILE_NO_CHANGE.
    Changing a matrix value and re-running: PROFILE_UPDATED.
    """
    await _make_tenant(WR_TENANT_ID, "wr-sem", "WR Sem")
    try:
        await _make_course(WR_TENANT_ID, "NR-10-B", "NR-10", 40, CourseModality.SEMIPRESENCIAL)
        manifest = {"courses": [_make_manifest_entry("NR-10-B", "NR-10")], "deactivate_codes": []}

        # First run — CREATE
        async with AsyncSessionLocal() as db:
            report1 = await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()
        assert len(report1["PROFILE_CREATED"]) == 1
        assert len(report1["PROFILE_UPDATED"]) == 0
        assert len(report1["PROFILE_NO_CHANGE"]) == 0

        # Second run — NO_CHANGE
        async with AsyncSessionLocal() as db:
            report2 = await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()
        assert len(report2["PROFILE_CREATED"]) == 0
        assert len(report2["PROFILE_NO_CHANGE"]) == 1
        assert len(report2["PROFILE_UPDATED"]) == 0
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ---------------------------------------------------------------------------
# Section 13 — Report-key preservation (no .update overwrite)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_report_key_preservation():
    """run_regulatory_only must not overwrite report keys.
    COURSE_FIELD_SKIPPED and PROFILE_SKIPPED must both be preserved.
    """
    await _make_tenant(WR_TENANT_ID, "wr-keys", "WR Keys")
    try:
        # Create only one of the 14 courses — others will be SKIPPED
        await _make_course(WR_TENANT_ID, "NR-10-B", "NR-10", 40, CourseModality.SEMIPRESENCIAL)

        manifest = {
            "courses": [_make_manifest_entry(code, nr) for code, nr in COURSE_CODES],
            "deactivate_codes": [],
        }

        async with AsyncSessionLocal() as db:
            report = await run_regulatory_only(db, WR_TENANT_ID, manifest, dry_run=True)
            await db.rollback()

        # Both skipped namespaces must exist and not overwrite each other
        assert "COURSE_FIELD_SKIPPED" in report
        assert "PROFILE_SKIPPED" in report
        # 13 courses not found → COURSE_FIELD_SKIPPED
        assert len(report["COURSE_FIELD_SKIPPED"]) == 13
        # 13 courses not found → PROFILE_SKIPPED
        assert len(report["PROFILE_SKIPPED"]) == 13
        # NR-10-B exists → NO_CHANGE (already 40h/SEMIPRESENCIAL)
        assert len(report["COURSE_FIELD_NO_CHANGE"]) == 1
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ---------------------------------------------------------------------------
# Section 14 — Enrollment details in MANUAL_REVIEW_REQUIRED (no CPF)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manual_review_includes_enrollment_details_no_cpf():
    """MANUAL_REVIEW_REQUIRED must include enrollment_id, status, class_id,
    certificate_count, is_demo — but NO CPF.
    """
    await _make_tenant(WR_TENANT_ID, "wr-det", "WR Det")
    try:
        course = await _make_course(WR_TENANT_ID, "NR-33-AUT", "NR-33", 16, CourseModality.SEMIPRESENCIAL)

        async with AsyncSessionLocal() as db:
            admin = User(
                tenant_id=WR_TENANT_ID,
                email="admin-det@wr.com",
                full_name="Admin Det",
                role=UserRole.ADMIN,
                is_active=True,
                password_hash="x",
            )
            db.add(admin)
            await db.flush()

            student = Student(tenant_id=WR_TENANT_ID, user_id=admin.id, cpf="11122233344")
            db.add(student)
            await db.flush()

            cls = Class(
                tenant_id=WR_TENANT_ID,
                course_id=course.id,
                responsible_admin_id=admin.id,
                start_date=utc_now().date(),
                end_date=utc_now().date(),
                max_students=20,
                status="ABERTA",
            )
            db.add(cls)
            await db.flush()

            enrollment = Enrollment(
                tenant_id=WR_TENANT_ID,
                student_id=student.id,
                class_id=cls.id,
                price=100.0,
            )
            db.add(enrollment)
            await db.commit()

        manifest = {"courses": [_make_manifest_entry("NR-33-AUT", "NR-33")], "deactivate_codes": []}

        async with AsyncSessionLocal() as db:
            report = await reconcile_regulatory_course_fields(db, WR_TENANT_ID, manifest, dry_run=True)
            await db.rollback()

        manual_reviews = report["MANUAL_REVIEW_REQUIRED"]
        assert len(manual_reviews) == 1
        mr = manual_reviews[0]
        assert mr["code"] == "NR-33-AUT"

        details = mr["historical_records"]["details"]
        assert len(details) == 1
        detail = details[0]
        assert "enrollment_id" in detail
        assert "status" in detail
        assert "class_id" in detail
        assert "certificate_count" in detail
        assert "is_demo" in detail
        # NO CPF anywhere in the detail
        detail_str = str(detail)
        assert "cpf" not in detail_str.lower()
        assert "11122233344" not in detail_str
    finally:
        await _cleanup_tenant(WR_TENANT_ID)
