"""Tests for regulatory revalidation rule: COMPLIANCE_READY + material change
→ REVIEW_REQUIRED. No auto-promote. ARCHIVED stays ARCHIVED.

Covers the FINAL REVALIDATION GATE:
A) READY + modality change → REVIEW_REQUIRED
B) READY + workload change → REVIEW_REQUIRED
C) READY + regulatory_version change → REVIEW_REQUIRED
D) READY + validity (matrix-owned) change → REVIEW_REQUIRED
E) READY + no regulatory change → stays READY (NO_CHANGE)
F) READY + only manual field different → stays READY (not a material change)
G) READY + new compliance blocker → REVIEW_REQUIRED
H) REVIEW_REQUIRED + blocker resolved → stays REVIEW_REQUIRED (no auto-promote)
I) ARCHIVED + regulatory change → stays ARCHIVED
J) Dry-run/apply parity: after apply, second dry-run shows NO_CHANGE but
   status stays REVIEW_REQUIRED
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
    plan_compliance_profile,
    reconcile_regulatory_compliance,
)

WR_TENANT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


def _make_manifest_entry(code: str, nr_family: str) -> dict:
    return {
        "code": code,
        "name": f"Test {code}",
        "nr_family": nr_family,
        "action": "CREATE",
        "content": {},
        "source_pdf": {"filename": "test.pdf", "sha256": "abc123", "pages": [1]},
    }


def _make_mock_existing_ready(
    delivery_mode: str = "PRESENCIAL",
    workload_minutes: int = 960,
    normative_minimum_minutes: int = 960,
    workload_source: str = WorkloadSource.NORMATIVE_MINIMUM,
    regulatory_standard: str = "NR-33",
    regulatory_version: str = "Trabalho em Espaço Confinado",
    requires_practical_component: bool = True,
    requires_final_assessment: bool = True,
    validity_period_months: int = 12,
    prerequisites: str | None = None,
    certificate_required_fields: list[str] | None = None,
    compliance_blockers: list[dict] | None = None,
    status: str = ComplianceStatus.COMPLIANCE_READY,
) -> MagicMock:
    """Create a mock COMPLIANCE_READY profile for pure planner tests."""
    existing = MagicMock()
    existing.status = status
    existing.delivery_mode = delivery_mode
    existing.workload_minutes = workload_minutes
    existing.normative_minimum_minutes = normative_minimum_minutes
    existing.workload_source = workload_source
    existing.regulatory_standard = regulatory_standard
    existing.regulatory_version = regulatory_version
    existing.requires_practical_component = requires_practical_component
    existing.requires_final_assessment = requires_final_assessment
    existing.validity_period_months = validity_period_months
    existing.prerequisites = prerequisites
    existing.certificate_required_fields = certificate_required_fields or []
    existing.compliance_blockers = compliance_blockers or []
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
# Test A: READY + modality change → REVIEW_REQUIRED
# ===========================================================================


def test_A_ready_modality_change_to_review():
    """A) existing COMPLIANCE_READY + delivery_mode=EAD, matrix=PRESENCIAL
    → UPDATED, target_status=REVIEW_REQUIRED.
    """
    course = MagicMock()
    course.carga_horaria = 16
    course.modality = CourseModality.PRESENCIAL

    existing = _make_mock_existing_ready(
        delivery_mode="EAD",  # wrong — matrix says PRESENCIAL
    )

    entry = _make_manifest_entry("NR-33-AUT", "NR-33")
    plan = plan_compliance_profile(course, entry, existing, force_review_required=False)

    assert plan.action == "UPDATED"
    assert plan.target_status == ComplianceStatus.REVIEW_REQUIRED

    # Status change must be in changes
    status_changes = [c for c in plan.changes if c["field"] == "status"]
    assert len(status_changes) == 1
    assert status_changes[0]["before"] == ComplianceStatus.COMPLIANCE_READY
    assert status_changes[0]["after"] == ComplianceStatus.REVIEW_REQUIRED

    # delivery_mode change must be in changes
    dm_changes = [c for c in plan.changes if c["field"] == "delivery_mode"]
    assert len(dm_changes) == 1
    assert dm_changes[0]["before"] == "EAD"
    assert dm_changes[0]["after"] == "PRESENCIAL"


# ===========================================================================
# Test B: READY + workload change → REVIEW_REQUIRED
# ===========================================================================


def test_B_ready_workload_change_to_review():
    """B) existing COMPLIANCE_READY + workload=16h, matrix=40h
    → UPDATED, target_status=REVIEW_REQUIRED.
    """
    course = MagicMock()
    course.carga_horaria = 40  # matrix will set workload_minutes=2400
    course.modality = CourseModality.PRESENCIAL

    existing = _make_mock_existing_ready(
        workload_minutes=960,  # 16h — wrong, matrix says 40h=2400min
        normative_minimum_minutes=960,
    )

    entry = _make_manifest_entry("NR-33-SUP", "NR-33")  # 40h normative minimum
    plan = plan_compliance_profile(course, entry, existing, force_review_required=False)

    assert plan.action == "UPDATED"
    assert plan.target_status == ComplianceStatus.REVIEW_REQUIRED

    wm_changes = [c for c in plan.changes if c["field"] == "workload_minutes"]
    assert len(wm_changes) == 1
    assert wm_changes[0]["before"] == 960
    assert wm_changes[0]["after"] == 2400


# ===========================================================================
# Test C: READY + regulatory_version change → REVIEW_REQUIRED
# ===========================================================================


def test_C_ready_regulatory_version_change_to_review():
    """C) existing COMPLIANCE_READY + regulatory_version changes
    → UPDATED, target_status=REVIEW_REQUIRED.
    """
    course = MagicMock()
    course.carga_horaria = 16
    course.modality = CourseModality.PRESENCIAL

    existing = _make_mock_existing_ready(
        regulatory_version="Old Version 2018",  # wrong — matrix has new version
    )

    entry = _make_manifest_entry("NR-33-AUT", "NR-33")
    plan = plan_compliance_profile(course, entry, existing, force_review_required=False)

    assert plan.action == "UPDATED"
    assert plan.target_status == ComplianceStatus.REVIEW_REQUIRED

    rv_changes = [c for c in plan.changes if c["field"] == "regulatory_version"]
    assert len(rv_changes) == 1
    assert rv_changes[0]["before"] == "Old Version 2018"


# ===========================================================================
# Test D: READY + validity (matrix-owned) change → REVIEW_REQUIRED
# ===========================================================================


def test_D_ready_validity_change_to_review():
    """D) existing COMPLIANCE_READY + validity=36, matrix=12
    → UPDATED, target_status=REVIEW_REQUIRED.
    """
    course = MagicMock()
    course.carga_horaria = 16
    course.modality = CourseModality.PRESENCIAL

    existing = _make_mock_existing_ready(
        validity_period_months=36,  # wrong — matrix says 12
    )

    entry = _make_manifest_entry("NR-33-AUT", "NR-33")
    plan = plan_compliance_profile(course, entry, existing, force_review_required=False)

    assert plan.action == "UPDATED"
    assert plan.target_status == ComplianceStatus.REVIEW_REQUIRED

    val_changes = [c for c in plan.changes if c["field"] == "validity_period_months"]
    assert len(val_changes) == 1
    assert val_changes[0]["before"] == 36
    assert val_changes[0]["after"] == 12


# ===========================================================================
# Test E: READY + no regulatory change → stays READY (NO_CHANGE)
# ===========================================================================


def test_E_ready_no_change_stays_ready():
    """E) existing COMPLIANCE_READY, no regulatory change
    → NO_CHANGE, stays COMPLIANCE_READY.
    """
    course = MagicMock()
    course.carga_horaria = 16
    course.modality = CourseModality.PRESENCIAL

    # All fields match matrix exactly
    existing = _make_mock_existing_ready(
        delivery_mode="PRESENCIAL",
        workload_minutes=960,
        normative_minimum_minutes=960,
        validity_period_months=12,
        compliance_blockers=[],
    )

    entry = _make_manifest_entry("NR-33-AUT", "NR-33")
    plan = plan_compliance_profile(course, entry, existing, force_review_required=False)

    assert plan.action == "NO_CHANGE"
    assert plan.target_status == ComplianceStatus.COMPLIANCE_READY


# ===========================================================================
# Test F: READY + only manual field different → stays READY
# ===========================================================================


def test_F_ready_manual_field_only_stays_ready():
    """F) existing COMPLIANCE_READY, only certificate_required_fields differs
    → reconciliation does NOT consider this a material change
    → stays COMPLIANCE_READY.
    """
    course = MagicMock()
    course.carga_horaria = 16
    course.modality = CourseModality.PRESENCIAL

    existing = _make_mock_existing_ready(
        delivery_mode="PRESENCIAL",
        workload_minutes=960,
        normative_minimum_minutes=960,
        validity_period_months=12,
        compliance_blockers=[],
        certificate_required_fields=["execution_date", "instructor"],  # manual field
    )

    entry = _make_manifest_entry("NR-33-AUT", "NR-33")
    plan = plan_compliance_profile(course, entry, existing, force_review_required=False)

    # certificate_required_fields is preserved (manual-owned), not a material change
    assert plan.action == "NO_CHANGE"
    assert plan.target_status == ComplianceStatus.COMPLIANCE_READY
    # cert fields preserved in target
    assert plan.target_state["certificate_required_fields"] == ["execution_date", "instructor"]


# ===========================================================================
# Test G: READY + new compliance blocker → REVIEW_REQUIRED
# ===========================================================================


def test_G_ready_new_blocker_to_review():
    """G) existing COMPLIANCE_READY, new compliance blocker added
    → REVIEW_REQUIRED.
    """
    course = MagicMock()
    course.carga_horaria = 16
    course.modality = CourseModality.SEMIPRESENCIAL

    # Profile is READY, no blockers, but Course diverges from matrix
    existing = _make_mock_existing_ready(
        delivery_mode="PRESENCIAL",  # matches matrix
        workload_minutes=960,
        normative_minimum_minutes=960,
        validity_period_months=12,
        compliance_blockers=[],
    )

    # force_review_required=True → history conflict blocker added
    entry = _make_manifest_entry("NR-33-AUT", "NR-33")
    plan = plan_compliance_profile(course, entry, existing, force_review_required=True)

    assert plan.target_status == ComplianceStatus.REVIEW_REQUIRED

    # Blocker added
    blocker_codes = [b["code"] for b in plan.target_blockers]
    assert BLOCKER_COURSE_FIELD_HISTORY_CONFLICT in blocker_codes


# ===========================================================================
# Test H: REVIEW_REQUIRED + blocker resolved → stays REVIEW_REQUIRED
# ===========================================================================


def test_H_review_required_blocker_resolved_no_auto_promote():
    """H) existing REVIEW_REQUIRED, blocker resolved (force_review=False)
    → stays REVIEW_REQUIRED (no auto-promote).
    """
    course = MagicMock()
    course.carga_horaria = 16
    course.modality = CourseModality.PRESENCIAL

    existing = _make_mock_existing_ready(
        delivery_mode="PRESENCIAL",
        workload_minutes=960,
        normative_minimum_minutes=960,
        validity_period_months=12,
        compliance_blockers=[_build_blocker(BLOCKER_COURSE_FIELD_HISTORY_CONFLICT)],
        status=ComplianceStatus.REVIEW_REQUIRED,
    )

    # force_review_required=False → blocker should be removed
    entry = _make_manifest_entry("NR-33-AUT", "NR-33")
    plan = plan_compliance_profile(course, entry, existing, force_review_required=False)

    # Blocker removed
    blocker_codes = [b["code"] for b in plan.target_blockers]
    assert BLOCKER_COURSE_FIELD_HISTORY_CONFLICT not in blocker_codes

    # Status stays REVIEW_REQUIRED (no auto-promote)
    assert plan.target_status == ComplianceStatus.REVIEW_REQUIRED


# ===========================================================================
# Test I: ARCHIVED + regulatory change → stays ARCHIVED
# ===========================================================================


def test_I_archived_regulatory_change_stays_archived():
    """I) existing ARCHIVED + regulatory field changes
    → stays ARCHIVED (never reactivated).
    """
    course = MagicMock()
    course.carga_horaria = 16
    course.modality = CourseModality.PRESENCIAL

    existing = _make_mock_existing_ready(
        delivery_mode="EAD",  # wrong — matrix says PRESENCIAL
        status=ComplianceStatus.ARCHIVED,
    )

    entry = _make_manifest_entry("NR-33-AUT", "NR-33")
    plan = plan_compliance_profile(course, entry, existing, force_review_required=False)

    # Stays ARCHIVED
    assert plan.target_status == ComplianceStatus.ARCHIVED

    # delivery_mode change is still reported (the field changes), but status
    # does not change to REVIEW_REQUIRED — it stays ARCHIVED
    dm_changes = [c for c in plan.changes if c["field"] == "delivery_mode"]
    assert len(dm_changes) == 1

    # Status NOT in changes (ARCHIVED → ARCHIVED is no change)
    status_changes = [c for c in plan.changes if c["field"] == "status"]
    assert len(status_changes) == 0


# ===========================================================================
# Test J: Dry-run/apply parity — second dry-run after apply shows NO_CHANGE
# but status stays REVIEW_REQUIRED
# ===========================================================================


@pytest.mark.asyncio
async def test_J_dry_run_apply_parity_revalidation():
    """J) After apply (READY→REVIEW_REQUIRED due to modality change), second
    dry-run shows NO_CHANGE for material fields, but status stays
    REVIEW_REQUIRED (no auto-promote).
    """
    await _make_tenant(WR_TENANT_ID, "wr-j-reval", "WR J Reval")
    try:
        course = await _make_course(WR_TENANT_ID, "NR-33-SUP", "NR-33", 40, CourseModality.PRESENCIAL)
        manifest = {"courses": [_make_manifest_entry("NR-33-SUP", "NR-33")], "deactivate_codes": []}

        # Pre-create COMPLIANCE_READY profile with wrong delivery_mode
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
                status=ComplianceStatus.COMPLIANCE_READY,
            )
            db.add(profile)
            await db.commit()

        # Dry-run → should show UPDATED with status READY→REVIEW_REQUIRED
        async with AsyncSessionLocal() as db:
            dry_report = await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=True)
            await db.rollback()

        assert len(dry_report["PROFILE_UPDATED"]) == 1
        updated = dry_report["PROFILE_UPDATED"][0]
        assert updated["status"] == ComplianceStatus.REVIEW_REQUIRED

        # Apply
        async with AsyncSessionLocal() as db:
            await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        # Verify DB: status=REVIEW_REQUIRED, delivery_mode=PRESENCIAL
        profile_after = await _get_profile(WR_TENANT_ID, "NR-33-SUP")
        assert profile_after.status == ComplianceStatus.REVIEW_REQUIRED
        assert profile_after.delivery_mode == "PRESENCIAL"

        # Second dry-run → NO_CHANGE (all material fields match), status stays REVIEW_REQUIRED
        async with AsyncSessionLocal() as db:
            dry_report_2 = await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=True)
            await db.rollback()

        assert len(dry_report_2["PROFILE_NO_CHANGE"]) == 1
        assert len(dry_report_2["PROFILE_UPDATED"]) == 0
        # Status stays REVIEW_REQUIRED (no auto-promote)
        assert dry_report_2["PROFILE_NO_CHANGE"][0]["status"] == ComplianceStatus.REVIEW_REQUIRED
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ===========================================================================
# Test K: NR18 blocker added to READY → REVIEW_REQUIRED
# ===========================================================================


def test_K_ready_nr18_blocker_to_review():
    """K) existing COMPLIANCE_READY for NR-18-F, matrix requires review
    → NR18 blocker added, status → REVIEW_REQUIRED.
    """
    course = MagicMock()
    course.carga_horaria = 4
    course.modality = CourseModality.EAD

    existing = _make_mock_existing_ready(
        regulatory_standard="NR-18",
        regulatory_version="Condições e Meio Ambiente de Trabalho na Indústria da Construção",
        delivery_mode="EAD",
        workload_source=WorkloadSource.REVIEW_REQUIRED,
        workload_minutes=240,
        normative_minimum_minutes=None,
        requires_practical_component=False,
        validity_period_months=None,
        compliance_blockers=[],
    )

    entry = _make_manifest_entry("NR-18-F", "NR-18")
    plan = plan_compliance_profile(course, entry, existing, force_review_required=False)

    # NR18 blocker added
    blocker_codes = [b["code"] for b in plan.target_blockers]
    assert BLOCKER_NR18_VARIANT_CONFIRMATION_REQUIRED in blocker_codes

    # Status → REVIEW_REQUIRED
    assert plan.target_status == ComplianceStatus.REVIEW_REQUIRED
