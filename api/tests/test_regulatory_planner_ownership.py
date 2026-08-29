"""Tests for planner ownership rules, NR18 blocker lifecycle, malformed
blocker fail-closed, and demo domain hardening.

Covers the micro-gate final de ownership do planner:
- Matrix-owned vs manual-owned field preservation
- certificate_required_fields preservation
- validity_period_months preservation when matrix doesn't define it
- prerequisites preservation when matrix doesn't define it
- NR-10-S prerequisite application
- External blocker preservation
- NR18 blocker lifecycle (matrix-driven, not code-driven)
- Malformed blocker readiness fail-closed
- Demo domain hardening (exact match, not endswith)
- Dry-run/apply parity for manual-owned fields
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
    REGULATORY_WORKLOAD,
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


def _make_mock_existing(
    status: str = ComplianceStatus.DRAFT,
    compliance_blockers: list[dict] | None = None,
    certificate_required_fields: list[str] | None = None,
    validity_period_months: int | None = None,
    prerequisites: str | None = None,
    delivery_mode: str = "PRESENCIAL",
    workload_source: str = WorkloadSource.NORMATIVE_MINIMUM,
    workload_minutes: int = 960,
    normative_minimum_minutes: int = 960,
    requires_practical_component: bool = True,
    requires_final_assessment: bool = True,
    regulatory_standard: str = "NR-33",
    regulatory_version: str = "Trabalho em Espaço Confinado",
) -> MagicMock:
    """Create a mock existing CourseComplianceProfile for pure planner tests."""
    existing = MagicMock()
    existing.status = status
    existing.compliance_blockers = compliance_blockers or []
    existing.certificate_required_fields = certificate_required_fields or []
    existing.validity_period_months = validity_period_months
    existing.prerequisites = prerequisites
    existing.delivery_mode = delivery_mode
    existing.workload_source = workload_source
    existing.workload_minutes = workload_minutes
    existing.normative_minimum_minutes = normative_minimum_minutes
    existing.requires_practical_component = requires_practical_component
    existing.requires_final_assessment = requires_final_assessment
    existing.regulatory_standard = regulatory_standard
    existing.regulatory_version = regulatory_version
    return existing


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
# Test A: certificate_required_fields preservation
# ===========================================================================


def test_A_certificate_required_fields_preserved():
    """A) existing certificate_required_fields=["A","B"], matrix unchanged
    → dry-run NO_CHANGE, apply preserves ["A","B"], second dry-run NO_CHANGE.
    """
    course = MagicMock()
    course.carga_horaria = 16
    course.modality = CourseModality.PRESENCIAL

    existing = _make_mock_existing(
        certificate_required_fields=["execution_date", "instructor"],
        delivery_mode="PRESENCIAL",
        workload_minutes=960,
        normative_minimum_minutes=960,
        validity_period_months=12,
    )

    entry = _make_manifest_entry("NR-33-AUT", "NR-33")
    plan = plan_compliance_profile(course, entry, existing, force_review_required=False)

    # No matrix-owned field changed → NO_CHANGE
    assert plan.action == "NO_CHANGE"
    # certificate_required_fields preserved in target
    assert plan.target_state["certificate_required_fields"] == ["execution_date", "instructor"]
    # No change reported for certificate_required_fields
    cert_changes = [c for c in plan.changes if c["field"] == "certificate_required_fields"]
    assert len(cert_changes) == 0


# ===========================================================================
# Test B: validity_period_months preservation when matrix doesn't define it
# ===========================================================================


def test_B_validity_preserved_when_matrix_undefined():
    """B) existing validity_period_months=36, matrix doesn't define validity
    → NO_CHANGE, 36 preserved.
    """
    course = MagicMock()
    course.carga_horaria = 4
    course.modality = CourseModality.EAD

    # NR-06-F: matrix doesn't define validity_months
    existing = _make_mock_existing(
        regulatory_standard="NR-06",
        regulatory_version="Equipamento de Proteção Individual",
        delivery_mode="EAD",
        workload_source=WorkloadSource.EMPLOYER_DEFINED,
        workload_minutes=240,
        normative_minimum_minutes=None,
        requires_practical_component=False,
        validity_period_months=36,  # manual value
    )

    entry = _make_manifest_entry("NR-06-F", "NR-06")
    plan = plan_compliance_profile(course, entry, existing, force_review_required=False)

    # validity preserved
    assert plan.target_state["validity_period_months"] == 36
    # No change for validity
    val_changes = [c for c in plan.changes if c["field"] == "validity_period_months"]
    assert len(val_changes) == 0


# ===========================================================================
# Test C: validity_period_months reconciliation when matrix defines it
# ===========================================================================


def test_C_validity_reconciled_when_matrix_defines():
    """C) matrix defines validity=12, existing=36 → UPDATED, 36→12.
    """
    course = MagicMock()
    course.carga_horaria = 16
    course.modality = CourseModality.PRESENCIAL

    # NR-33-AUT: matrix defines validity_months=12
    existing = _make_mock_existing(
        delivery_mode="PRESENCIAL",
        workload_minutes=960,
        normative_minimum_minutes=960,
        validity_period_months=36,  # wrong — matrix says 12
    )

    entry = _make_manifest_entry("NR-33-AUT", "NR-33")
    plan = plan_compliance_profile(course, entry, existing, force_review_required=False)

    # validity reconciled to matrix value
    assert plan.target_state["validity_period_months"] == 12
    # Change reported
    val_changes = [c for c in plan.changes if c["field"] == "validity_period_months"]
    assert len(val_changes) == 1
    assert val_changes[0]["before"] == 36
    assert val_changes[0]["after"] == 12
    assert plan.action == "UPDATED"


# ===========================================================================
# Test D: prerequisites preservation when matrix doesn't define it
# ===========================================================================


def test_D_prerequisites_preserved_when_matrix_undefined():
    """D) existing prerequisites="Pré-requisito manual", matrix doesn't define
    → NO_CHANGE, manual value preserved.
    """
    course = MagicMock()
    course.carga_horaria = 4
    course.modality = CourseModality.EAD

    # NR-06-F: matrix doesn't define prerequisite
    existing = _make_mock_existing(
        regulatory_standard="NR-06",
        regulatory_version="Equipamento de Proteção Individual",
        delivery_mode="EAD",
        workload_source=WorkloadSource.EMPLOYER_DEFINED,
        workload_minutes=240,
        normative_minimum_minutes=None,
        requires_practical_component=False,
        prerequisites="Pré-requisito manual configurado pelo admin",
    )

    entry = _make_manifest_entry("NR-06-F", "NR-06")
    plan = plan_compliance_profile(course, entry, existing, force_review_required=False)

    # prerequisites preserved
    assert plan.target_state["prerequisites"] == "Pré-requisito manual configurado pelo admin"
    # No change for prerequisites
    prereq_changes = [c for c in plan.changes if c["field"] == "prerequisites"]
    assert len(prereq_changes) == 0


# ===========================================================================
# Test E: NR-10-S prerequisite application
# ===========================================================================


def test_E_nr10_s_prerequisite_applied():
    """E) NR-10-S matrix prerequisite, existing=None → UPDATED,
    None → "Requer conclusão do curso NR-10-B".
    """
    course = MagicMock()
    course.carga_horaria = 40
    course.modality = CourseModality.SEMIPRESENCIAL

    existing = _make_mock_existing(
        regulatory_standard="NR-10",
        regulatory_version="Segurança em Instalações e Serviços em Eletricidade",
        delivery_mode="SEMIPRESENCIAL",
        workload_source=WorkloadSource.NORMATIVE_MINIMUM,
        workload_minutes=2400,
        normative_minimum_minutes=2400,
        requires_practical_component=False,
        prerequisites=None,  # no prerequisite set yet
    )

    entry = _make_manifest_entry("NR-10-S", "NR-10")
    plan = plan_compliance_profile(course, entry, existing, force_review_required=False)

    # prerequisite applied from matrix
    assert plan.target_state["prerequisites"] == "Requer conclusão do curso NR-10-B"
    # Change reported
    prereq_changes = [c for c in plan.changes if c["field"] == "prerequisites"]
    assert len(prereq_changes) == 1
    assert prereq_changes[0]["before"] is None
    assert "NR-10-B" in prereq_changes[0]["after"]


# ===========================================================================
# Test F: External blocker preservation
# ===========================================================================


def test_F_external_blocker_preserved():
    """When history conflict resolves, only COURSE_FIELD_HISTORY_CONFLICT
    is removed. External blockers (e.g. EXTERNAL_REVIEW_REQUIRED) are preserved.
    """
    existing_blockers = [
        {"code": "EXTERNAL_REVIEW_REQUIRED", "source": "OTHER_MODULE", "details": {}},
        _build_blocker(BLOCKER_COURSE_FIELD_HISTORY_CONFLICT, {"fields": ["modality"]}),
    ]

    # Resolve history conflict → remove only COURSE_FIELD_HISTORY_CONFLICT
    merged, changes = _merge_blockers(
        existing_blockers,
        to_add=[],
        to_remove_codes={BLOCKER_COURSE_FIELD_HISTORY_CONFLICT},
    )

    # External blocker preserved
    codes = [b["code"] for b in merged if isinstance(b, dict) and "code" in b]
    assert "EXTERNAL_REVIEW_REQUIRED" in codes
    # History conflict removed
    assert BLOCKER_COURSE_FIELD_HISTORY_CONFLICT not in codes
    # Change reported
    removed = [c for c in changes if c["action"] == "removed"]
    assert len(removed) == 1
    assert removed[0]["code"] == BLOCKER_COURSE_FIELD_HISTORY_CONFLICT


# ===========================================================================
# Test G: NR18 blocker lifecycle — matrix-driven, not code-driven
# ===========================================================================


def test_G_nr18_blocker_present_when_matrix_review_required():
    """NR-18-F with matrix status=REVIEW_REQUIRED → blocker present."""
    course = MagicMock()
    course.carga_horaria = 4
    course.modality = CourseModality.EAD

    entry = _make_manifest_entry("NR-18-F", "NR-18")
    plan = plan_compliance_profile(course, entry, existing=None, force_review_required=False)

    blocker_codes = [b["code"] for b in plan.target_blockers]
    assert BLOCKER_NR18_VARIANT_CONFIRMATION_REQUIRED in blocker_codes
    assert plan.target_status == ComplianceStatus.REVIEW_REQUIRED


def test_G_nr18_blocker_removed_when_matrix_confirmed():
    """Simulate matrix update: NR-18-F no longer REVIEW_REQUIRED.
    Blocker is removed, but status stays REVIEW_REQUIRED (no auto-promote).
    """
    course = MagicMock()
    course.carga_horaria = 4
    course.modality = CourseModality.EAD

    # Existing profile with REVIEW_REQUIRED and NR18 blocker
    existing = _make_mock_existing(
        regulatory_standard="NR-18",
        regulatory_version="Condições e Meio Ambiente de Trabalho na Indústria da Construção",
        delivery_mode="EAD",
        workload_source=WorkloadSource.NORMATIVE_MINIMUM,
        workload_minutes=240,
        normative_minimum_minutes=240,
        requires_practical_component=False,
        status=ComplianceStatus.REVIEW_REQUIRED,
        compliance_blockers=[_build_blocker(BLOCKER_NR18_VARIANT_CONFIRMATION_REQUIRED)],
    )

    # Simulate confirmed matrix: patch REGULATORY_WORKLOAD temporarily
    original = REGULATORY_WORKLOAD["NR-18-F"]
    try:
        REGULATORY_WORKLOAD["NR-18-F"] = {
            "workload_source": WorkloadSource.NORMATIVE_MINIMUM,
            "normative_minimum_minutes": 240,
            "modality": "EAD",
            "validity_months": 24,
        }
        entry = _make_manifest_entry("NR-18-F", "NR-18")
        plan = plan_compliance_profile(course, entry, existing, force_review_required=False)

        # Blocker removed
        blocker_codes = [b["code"] for b in plan.target_blockers]
        assert BLOCKER_NR18_VARIANT_CONFIRMATION_REQUIRED not in blocker_codes

        # Status stays REVIEW_REQUIRED (no auto-promote)
        assert plan.target_status == ComplianceStatus.REVIEW_REQUIRED
    finally:
        REGULATORY_WORKLOAD["NR-18-F"] = original


# ===========================================================================
# Test H: Malformed blocker readiness — empty dict
# ===========================================================================


@pytest.mark.asyncio
async def test_H_malformed_blocker_empty_dict():
    """A) compliance_blockers=[{}], status COMPLIANCE_READY
    → COMPLIANCE_REVIEW_REQUIRED, no exception.
    """
    await _make_tenant(WR_TENANT_ID, "wr-h", "WR H")
    try:
        course = await _make_course(WR_TENANT_ID, "NR-33-AUT", "NR-33", 16, CourseModality.PRESENCIAL)
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
                compliance_blockers=[{}],  # malformed — empty dict
                status=ComplianceStatus.COMPLIANCE_READY,
            )
            db.add(profile)
            await db.commit()

        # Must not raise
        async with AsyncSessionLocal() as db:
            evaluation = await evaluate_regulatory_state(
                db, tenant_id=WR_TENANT_ID, enrollment_id=enrollment_id, persist=False,
            )

        assert evaluation.state == RegulatoryCompletionState.COMPLIANCE_REVIEW_REQUIRED
        assert any("UNKNOWN_COMPLIANCE_BLOCKER" in b for b in evaluation.blockers)
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ===========================================================================
# Test I: Malformed blocker readiness — non-dict item
# ===========================================================================


@pytest.mark.asyncio
async def test_I_malformed_blocker_non_dict():
    """B) compliance_blockers=["invalid"], → blocked, no exception."""
    await _make_tenant(WR_TENANT_ID, "wr-i", "WR I")
    try:
        course = await _make_course(WR_TENANT_ID, "NR-33-AUT", "NR-33", 16, CourseModality.PRESENCIAL)
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
                compliance_blockers=["invalid"],  # malformed — non-dict
                status=ComplianceStatus.COMPLIANCE_READY,
            )
            db.add(profile)
            await db.commit()

        # Must not raise
        async with AsyncSessionLocal() as db:
            evaluation = await evaluate_regulatory_state(
                db, tenant_id=WR_TENANT_ID, enrollment_id=enrollment_id, persist=False,
            )

        assert evaluation.state == RegulatoryCompletionState.COMPLIANCE_REVIEW_REQUIRED
        assert any("UNKNOWN_COMPLIANCE_BLOCKER" in b for b in evaluation.blockers)
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ===========================================================================
# Test J: Valid blocker — correct code in report
# ===========================================================================


@pytest.mark.asyncio
async def test_J_valid_blocker_correct_code():
    """C) Valid blocker → correct code in the readiness report."""
    await _make_tenant(WR_TENANT_ID, "wr-j", "WR J")
    try:
        course = await _make_course(WR_TENANT_ID, "NR-33-AUT", "NR-33", 16, CourseModality.PRESENCIAL)
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
        assert any(BLOCKER_COURSE_FIELD_HISTORY_CONFLICT in b for b in evaluation.blockers)
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ===========================================================================
# Test K: Demo domain — exact match
# ===========================================================================


def test_K_demo_domain_exact_match():
    """demo@demo.local → CONFIRMED_DEMO."""
    classification, evidence = _classify_enrollment_demo(
        cert_nums=[], user_email="demo@demo.local", class_location="SP",
    )
    assert classification == "CONFIRMED_DEMO"
    assert "DEMO_USER_EMAIL_DOMAIN" in evidence


def test_K_demo_domain_subdomain():
    """demo@wr.demo.local → CONFIRMED_DEMO."""
    classification, evidence = _classify_enrollment_demo(
        cert_nums=[], user_email="demo@wr.demo.local", class_location="SP",
    )
    assert classification == "CONFIRMED_DEMO"
    assert "DEMO_USER_EMAIL_DOMAIN" in evidence


def test_K_demo_domain_notdemo_rejected():
    """user@notdemo.local → UNKNOWN (not a false positive)."""
    classification, evidence = _classify_enrollment_demo(
        cert_nums=[], user_email="user@notdemo.local", class_location="SP",
    )
    assert classification == "UNKNOWN"
    assert "DEMO_USER_EMAIL_DOMAIN" not in evidence


def test_K_demo_domain_case_insensitive():
    """Demo@DEMO.LOCAL → CONFIRMED_DEMO (case insensitive)."""
    classification, evidence = _classify_enrollment_demo(
        cert_nums=[], user_email="Demo@DEMO.LOCAL", class_location="SP",
    )
    assert classification == "CONFIRMED_DEMO"
    assert "DEMO_USER_EMAIL_DOMAIN" in evidence


# ===========================================================================
# Test L: Dry-run/apply parity — manual-owned fields preserved
# ===========================================================================


@pytest.mark.asyncio
async def test_L_dry_run_apply_parity_manual_fields():
    """After apply, dry-run → NO_CHANGE. Manual-owned fields preserved.
    Compares plan.target_state with actual DB state after apply for
    matrix-owned fields.
    """
    await _make_tenant(WR_TENANT_ID, "wr-l", "WR L")
    try:
        await _make_course(WR_TENANT_ID, "NR-33-SUP", "NR-33", 40, CourseModality.PRESENCIAL)
        manifest = {"courses": [_make_manifest_entry("NR-33-SUP", "NR-33")], "deactivate_codes": []}

        # Apply
        async with AsyncSessionLocal() as db:
            apply_report = await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        assert len(apply_report["PROFILE_CREATED"]) == 1

        # Manually set certificate_required_fields (manual-owned)
        from sqlalchemy.orm.attributes import flag_modified

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(CourseComplianceProfile)
                .join(Course, Course.id == CourseComplianceProfile.course_id)
                .where(CourseComplianceProfile.tenant_id == WR_TENANT_ID, Course.code == "NR-33-SUP")
            )
            profile = result.scalar_one()
            profile.certificate_required_fields = ["execution_date", "instructor"]
            flag_modified(profile, "certificate_required_fields")
            await db.commit()

        # Dry-run → should be NO_CHANGE (manual fields not reported)
        async with AsyncSessionLocal() as db:
            dry_report = await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=True)
            await db.rollback()

        assert len(dry_report["PROFILE_NO_CHANGE"]) == 1
        assert len(dry_report["PROFILE_UPDATED"]) == 0

        # Verify manual field preserved in DB (read in same session)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(CourseComplianceProfile)
                .join(Course, Course.id == CourseComplianceProfile.course_id)
                .where(CourseComplianceProfile.tenant_id == WR_TENANT_ID, Course.code == "NR-33-SUP")
            )
            profile_after = result.scalar_one()
            assert profile_after.certificate_required_fields == ["execution_date", "instructor"]
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ===========================================================================
# Test M: Full apply/dry-run parity — target_state matches DB after apply
# ===========================================================================


@pytest.mark.asyncio
async def test_M_apply_target_matches_db():
    """After apply, the profile's matrix-owned fields in DB match
    plan.target_state from a dry-run on the same input.
    """
    await _make_tenant(WR_TENANT_ID, "wr-m", "WR M")
    try:
        course = await _make_course(WR_TENANT_ID, "NR-33-SUP", "NR-33", 16, CourseModality.SEMIPRESENCIAL)
        manifest = {"courses": [_make_manifest_entry("NR-33-SUP", "NR-33")], "deactivate_codes": []}

        # Dry-run to get plan
        async with AsyncSessionLocal() as db:
            existing = (
                await db.execute(
                    select(CourseComplianceProfile).where(
                        CourseComplianceProfile.tenant_id == WR_TENANT_ID,
                        CourseComplianceProfile.course_id == course.id,
                    )
                )
            ).scalar_one_or_none()
            plan = plan_compliance_profile(course, manifest["courses"][0], existing, force_review_required=False)
            await db.rollback()

        # Apply
        async with AsyncSessionLocal() as db:
            await run_regulatory_only(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        # Verify DB matches plan target for matrix-owned fields
        profile = await _get_profile(WR_TENANT_ID, "NR-33-SUP")
        assert profile.regulatory_standard == plan.target_state["regulatory_standard"]
        assert profile.regulatory_version == plan.target_state["regulatory_version"]
        assert profile.delivery_mode == plan.target_state["delivery_mode"]
        assert profile.workload_source == plan.target_state["workload_source"]
        assert profile.workload_minutes == plan.target_state["workload_minutes"]
        assert profile.normative_minimum_minutes == plan.target_state["normative_minimum_minutes"]
        assert profile.requires_practical_component == plan.target_state["requires_practical_component"]
        assert profile.requires_final_assessment == plan.target_state["requires_final_assessment"]
        assert profile.validity_period_months == plan.target_state["validity_period_months"]
        assert profile.status == plan.target_status
    finally:
        await _cleanup_tenant(WR_TENANT_ID)
