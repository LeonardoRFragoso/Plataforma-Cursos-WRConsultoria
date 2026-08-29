"""Tests for safe regulatory Course field alignment with REGULATORY_WORKLOAD.

Covers:
- Gap proof: reconcile_regulatory_compliance does NOT update Course fields
- reconcile_regulatory_course_fields aligns Course.carga_horaria/modality safely
- EMPLOYER_DEFINED / PLH_DEFINED protection
- NR-18-F fail-closed (REVIEW_REQUIRED, no Course mutation)
- technical_responsible_id stays NULL
- Idempotency
- Out-of-14-codes isolation
- Tenant isolation
- Historical snapshot safety (MANUAL_REVIEW_REQUIRED)
- Final 14-profile count with correct statuses
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
from app.models.enrollment import Enrollment
from app.models.student import Student
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User, UserRole
from app.scripts.import_wr_catalog import (
    reconcile_regulatory_compliance,
    reconcile_regulatory_course_fields,
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
# Section 1 — Gap proof: current reconcile does NOT update Course fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gap_reconcile_does_not_update_course_fields():
    """PROOF: reconcile_regulatory_compliance creates the profile with correct
    regulatory values but does NOT align Course.carga_horaria or Course.modality.

    NR-33-SUP starts at 16h / SEMIPRESENCIAL (wrong per matrix).
    After reconcile, the profile is correct (40h / PRESENCIAL) but the Course
    remains 16h / SEMIPRESENCIAL — confirming the gap.
    """
    await _make_tenant(WR_TENANT_ID, "wr-gap", "WR Gap Test")
    try:
        await _make_course(WR_TENANT_ID, "NR-33-SUP", "NR-33", 16, CourseModality.SEMIPRESENCIAL)
        manifest = {"courses": [_make_manifest_entry("NR-33-SUP", "NR-33")], "deactivate_codes": []}

        async with AsyncSessionLocal() as db:
            await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        course = await _get_course(WR_TENANT_ID, "NR-33-SUP")
        profile = await _get_profile(WR_TENANT_ID, "NR-33-SUP")

        # Gap: Course NOT aligned
        assert course.carga_horaria == 16, "Course.carga_horaria was not updated by reconcile (gap)"
        assert course.modality == CourseModality.SEMIPRESENCIAL, "Course.modality was not updated by reconcile (gap)"

        # Profile IS correct
        assert profile is not None
        assert profile.workload_minutes == 2400
        assert profile.delivery_mode == "PRESENCIAL"
        assert profile.normative_minimum_minutes == 2400
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ---------------------------------------------------------------------------
# Section 3+4 — reconcile_regulatory_course_fields aligns Course safely
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_A_nr33_aut_modality_aligned_workload_unchanged():
    """A) NR-33-AUT: SEMIPRESENCIAL → PRESENCIAL. 16h stays 16h (matrix minimum is 16h)."""
    await _make_tenant(WR_TENANT_ID, "wr-a", "WR A")
    try:
        await _make_course(WR_TENANT_ID, "NR-33-AUT", "NR-33", 16, CourseModality.SEMIPRESENCIAL)
        manifest = {"courses": [_make_manifest_entry("NR-33-AUT", "NR-33")], "deactivate_codes": []}

        async with AsyncSessionLocal() as db:
            await reconcile_regulatory_course_fields(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        course = await _get_course(WR_TENANT_ID, "NR-33-AUT")
        assert course.modality == CourseModality.PRESENCIAL
        assert course.carga_horaria == 16  # 16h is the normative minimum — no change needed
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


@pytest.mark.asyncio
async def test_B_nr33_sup_workload_and_modality_aligned():
    """B) NR-33-SUP: 16h + SEMIPRESENCIAL → 40h + PRESENCIAL."""
    await _make_tenant(WR_TENANT_ID, "wr-b", "WR B")
    try:
        await _make_course(WR_TENANT_ID, "NR-33-SUP", "NR-33", 16, CourseModality.SEMIPRESENCIAL)
        manifest = {"courses": [_make_manifest_entry("NR-33-SUP", "NR-33")], "deactivate_codes": []}

        async with AsyncSessionLocal() as db:
            await reconcile_regulatory_course_fields(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        course = await _get_course(WR_TENANT_ID, "NR-33-SUP")
        assert course.carga_horaria == 40
        assert course.modality == CourseModality.PRESENCIAL
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


@pytest.mark.asyncio
async def test_C_nr35_f_modality_aligned_workload_unchanged():
    """C) NR-35-F: SEMIPRESENCIAL → PRESENCIAL. 8h stays 8h."""
    await _make_tenant(WR_TENANT_ID, "wr-c", "WR C")
    try:
        await _make_course(WR_TENANT_ID, "NR-35-F", "NR-35", 8, CourseModality.SEMIPRESENCIAL)
        manifest = {"courses": [_make_manifest_entry("NR-35-F", "NR-35")], "deactivate_codes": []}

        async with AsyncSessionLocal() as db:
            await reconcile_regulatory_course_fields(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        course = await _get_course(WR_TENANT_ID, "NR-35-F")
        assert course.modality == CourseModality.PRESENCIAL
        assert course.carga_horaria == 8
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


@pytest.mark.asyncio
async def test_D_nr10_b_and_s_workload_aligned():
    """D) NR-10-B and NR-10-S → 40h."""
    await _make_tenant(WR_TENANT_ID, "wr-d", "WR D")
    try:
        await _make_course(WR_TENANT_ID, "NR-10-B", "NR-10", 4, CourseModality.EAD)
        await _make_course(WR_TENANT_ID, "NR-10-S", "NR-10", 4, CourseModality.EAD)
        manifest = {
            "courses": [
                _make_manifest_entry("NR-10-B", "NR-10"),
                _make_manifest_entry("NR-10-S", "NR-10"),
            ],
            "deactivate_codes": [],
        }

        async with AsyncSessionLocal() as db:
            await reconcile_regulatory_course_fields(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        b = await _get_course(WR_TENANT_ID, "NR-10-B")
        s = await _get_course(WR_TENANT_ID, "NR-10-S")
        assert b.carga_horaria == 40
        assert s.carga_horaria == 40
        # NR-10 modality in matrix is SEMIPRESENCIAL
        assert b.modality == CourseModality.SEMIPRESENCIAL
        assert s.modality == CourseModality.SEMIPRESENCIAL
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


@pytest.mark.asyncio
async def test_E_nr06_f_employer_defined_not_converted():
    """E) NR-06-F: workload_source=EMPLOYER_DEFINED → 4h must NOT become normative minimum."""
    await _make_tenant(WR_TENANT_ID, "wr-e", "WR E")
    try:
        await _make_course(WR_TENANT_ID, "NR-06-F", "NR-06", 4, CourseModality.EAD)
        manifest = {"courses": [_make_manifest_entry("NR-06-F", "NR-06")], "deactivate_codes": []}

        async with AsyncSessionLocal() as db:
            await reconcile_regulatory_course_fields(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        course = await _get_course(WR_TENANT_ID, "NR-06-F")
        assert course.carga_horaria == 4  # unchanged — employer-defined
        # modality IS EAD per matrix, so it stays EAD (no change needed)
        assert course.modality == CourseModality.EAD
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


@pytest.mark.asyncio
async def test_F_nr11_variants_not_treated_as_normative():
    """F) NR-11 variants: 16h must NOT be treated as normative minimum."""
    await _make_tenant(WR_TENANT_ID, "wr-f", "WR F")
    try:
        codes = ["NR-11-EMP", "NR-11-GUI", "NR-11-MIN", "NR-11-PLA", "NR-11-PON", "NR-11-RET"]
        for code in codes:
            await _make_course(WR_TENANT_ID, code, "NR-11", 16, CourseModality.SEMIPRESENCIAL)
        manifest = {
            "courses": [_make_manifest_entry(c, "NR-11") for c in codes],
            "deactivate_codes": [],
        }

        async with AsyncSessionLocal() as db:
            await reconcile_regulatory_course_fields(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        for code in codes:
            course = await _get_course(WR_TENANT_ID, code)
            assert course.carga_horaria == 16  # unchanged — employer-defined
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


@pytest.mark.asyncio
async def test_G_nr12_f_plh_defined_not_converted():
    """G) NR-12-F: workload_source=PLH_DEFINED → 12h must NOT become normative minimum."""
    await _make_tenant(WR_TENANT_ID, "wr-g", "WR G")
    try:
        await _make_course(WR_TENANT_ID, "NR-12-F", "NR-12", 12, CourseModality.SEMIPRESENCIAL)
        manifest = {"courses": [_make_manifest_entry("NR-12-F", "NR-12")], "deactivate_codes": []}

        async with AsyncSessionLocal() as db:
            await reconcile_regulatory_course_fields(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        course = await _get_course(WR_TENANT_ID, "NR-12-F")
        assert course.carga_horaria == 12  # unchanged — PLH-defined
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


@pytest.mark.asyncio
async def test_H_nr18_f_course_not_modified_profile_review_required():
    """H) NR-18-F: Course workload/modality NOT altered. Profile status=REVIEW_REQUIRED."""
    await _make_tenant(WR_TENANT_ID, "wr-h", "WR H")
    try:
        await _make_course(WR_TENANT_ID, "NR-18-F", "NR-18", 4, CourseModality.EAD)
        manifest = {"courses": [_make_manifest_entry("NR-18-F", "NR-18")], "deactivate_codes": []}

        async with AsyncSessionLocal() as db:
            await reconcile_regulatory_course_fields(db, WR_TENANT_ID, manifest, dry_run=False)
            await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        course = await _get_course(WR_TENANT_ID, "NR-18-F")
        assert course.carga_horaria == 4  # unchanged
        assert course.modality == CourseModality.EAD  # unchanged (matrix modality is None)

        profile = await _get_profile(WR_TENANT_ID, "NR-18-F")
        assert profile is not None
        assert profile.status == ComplianceStatus.REVIEW_REQUIRED
        assert profile.workload_source == WorkloadSource.REVIEW_REQUIRED
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


@pytest.mark.asyncio
async def test_I_technical_responsible_id_stays_null():
    """I) technical_responsible_id stays NULL after reconciliation — no invented professional."""
    await _make_tenant(WR_TENANT_ID, "wr-i", "WR I")
    try:
        await _make_course(WR_TENANT_ID, "NR-33-SUP", "NR-33", 16, CourseModality.SEMIPRESENCIAL)
        manifest = {"courses": [_make_manifest_entry("NR-33-SUP", "NR-33")], "deactivate_codes": []}

        async with AsyncSessionLocal() as db:
            await reconcile_regulatory_course_fields(db, WR_TENANT_ID, manifest, dry_run=False)
            await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        profile = await _get_profile(WR_TENANT_ID, "NR-33-SUP")
        assert profile is not None
        assert profile.technical_responsible_id is None
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


@pytest.mark.asyncio
async def test_J_idempotency_second_run_no_updates():
    """J) Second execution: 0 course updates, 0 duplicate profiles."""
    await _make_tenant(WR_TENANT_ID, "wr-j", "WR J")
    try:
        await _make_course(WR_TENANT_ID, "NR-33-SUP", "NR-33", 16, CourseModality.SEMIPRESENCIAL)
        manifest = {"courses": [_make_manifest_entry("NR-33-SUP", "NR-33")], "deactivate_codes": []}

        async with AsyncSessionLocal() as db:
            await reconcile_regulatory_course_fields(db, WR_TENANT_ID, manifest, dry_run=False)
            await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        # Second run
        async with AsyncSessionLocal() as db:
            field_report = await reconcile_regulatory_course_fields(db, WR_TENANT_ID, manifest, dry_run=False)
            comp_report = await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        assert len(field_report["COURSE_FIELD_UPDATES"]) == 0
        # compliance report should not create duplicates
        assert len(comp_report.get("PROFILE_CREATED", [])) == 0 or all(
            not item.get("dry_run") for item in comp_report.get("PROFILE_CREATED", [])
        )

        # Verify single profile
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(CourseComplianceProfile)
                .join(Course, Course.id == CourseComplianceProfile.course_id)
                .where(CourseComplianceProfile.tenant_id == WR_TENANT_ID, Course.code == "NR-33-SUP")
            )
            profiles = result.scalars().all()
        assert len(profiles) == 1
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


@pytest.mark.asyncio
async def test_K_course_outside_14_codes_not_altered():
    """K) A course code outside the 14 regulatory codes → no alteration."""
    await _make_tenant(WR_TENANT_ID, "wr-k", "WR K")
    try:
        await _make_course(WR_TENANT_ID, "NR-20-F", "NR-20", 16, CourseModality.EAD)
        manifest = {"courses": [_make_manifest_entry("NR-20-F", "NR-20")], "deactivate_codes": []}

        async with AsyncSessionLocal() as db:
            field_report = await reconcile_regulatory_course_fields(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        course = await _get_course(WR_TENANT_ID, "NR-20-F")
        assert course.carga_horaria == 16  # unchanged
        assert course.modality == CourseModality.EAD  # unchanged
        assert len(field_report["COURSE_FIELD_UPDATES"]) == 0
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


@pytest.mark.asyncio
async def test_L_different_tenant_not_altered():
    """L) A different tenant → no alteration."""
    await _make_tenant(WR_TENANT_ID, "wr-l", "WR L")
    await _make_tenant(OTHER_TENANT_ID, "other-l", "Other L")
    try:
        await _make_course(OTHER_TENANT_ID, "NR-33-SUP", "NR-33", 16, CourseModality.SEMIPRESENCIAL)
        manifest = {"courses": [_make_manifest_entry("NR-33-SUP", "NR-33")], "deactivate_codes": []}

        async with AsyncSessionLocal() as db:
            field_report = await reconcile_regulatory_course_fields(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        course = await _get_course(OTHER_TENANT_ID, "NR-33-SUP")
        assert course.carga_horaria == 16  # unchanged — different tenant
        assert course.modality == CourseModality.SEMIPRESENCIAL
        assert len(field_report["COURSE_FIELD_UPDATES"]) == 0
    finally:
        await _cleanup_tenant(WR_TENANT_ID)
        await _cleanup_tenant(OTHER_TENANT_ID)


# ---------------------------------------------------------------------------
# Section 10 — Historical snapshot safety
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_historical_certificates_trigger_manual_review():
    """If certificates exist for a course, Course field changes are flagged
    MANUAL_REVIEW_REQUIRED and NOT applied silently."""
    await _make_tenant(WR_TENANT_ID, "wr-hist", "WR Hist")
    try:
        course = await _make_course(WR_TENANT_ID, "NR-33-SUP", "NR-33", 16, CourseModality.SEMIPRESENCIAL)

        # Create a class + student + enrollment + certificate to simulate historical data
        async with AsyncSessionLocal() as db:
            admin = User(
                tenant_id=WR_TENANT_ID,
                email="admin-hist@wr.com",
                full_name="Admin Hist",
                role=UserRole.ADMIN,
                is_active=True,
                password_hash="x",
            )
            db.add(admin)
            await db.flush()

            student = Student(
                tenant_id=WR_TENANT_ID,
                user_id=admin.id,
                cpf="11122233344",
            )
            db.add(student)
            await db.flush()

            cls = Class(
                tenant_id=WR_TENANT_ID,
                course_id=course.id,
                responsible_admin_id=admin.id,
                start_date=utc_now().date(),
                end_date=utc_now().date(),
                max_students=20,
                location="SP",
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
            await db.flush()

            cert = Certificate(
                tenant_id=WR_TENANT_ID,
                enrollment_id=enrollment.id,
                certificate_number="HIST-001",
                validation_code="HIST-VAL-001",
                status="ACTIVE",
            )
            db.add(cert)
            await db.commit()

        manifest = {"courses": [_make_manifest_entry("NR-33-SUP", "NR-33")], "deactivate_codes": []}

        async with AsyncSessionLocal() as db:
            field_report = await reconcile_regulatory_course_fields(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

        # Course NOT modified — manual review required
        course_after = await _get_course(WR_TENANT_ID, "NR-33-SUP")
        assert course_after.carga_horaria == 16
        assert course_after.modality == CourseModality.SEMIPRESENCIAL

        # Report flags MANUAL_REVIEW_REQUIRED
        manual_reviews = field_report.get("MANUAL_REVIEW_REQUIRED", [])
        assert any(item["code"] == "NR-33-SUP" for item in manual_reviews)
    finally:
        # Cleanup certificates/enrollments/classes/students first (FK constraints)
        async with AsyncSessionLocal() as db:
            await db.execute(delete(Certificate).where(Certificate.tenant_id == WR_TENANT_ID))
            await db.execute(delete(Enrollment).where(Enrollment.tenant_id == WR_TENANT_ID))
            await db.execute(delete(Student).where(Student.tenant_id == WR_TENANT_ID))
            await db.execute(delete(Class).where(Class.tenant_id == WR_TENANT_ID))
            await db.commit()
        await _cleanup_tenant(WR_TENANT_ID)


# ---------------------------------------------------------------------------
# Section 12 — Final 14-profile count with correct statuses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_final_14_profiles_correct_statuses():
    """After full alignment + reconciliation for all 14 courses:
    - 14 CourseComplianceProfile records
    - NR-18-F: REVIEW_REQUIRED
    - All others: DRAFT (none APPROVED automatically)
    - technical_responsible_id NULL for all
    """
    await _make_tenant(WR_TENANT_ID, "wr-14", "WR 14")
    try:
        for code, nr_family in COURSE_CODES:
            # Start with deliberately wrong values to prove alignment
            await _make_course(WR_TENANT_ID, code, nr_family, 8, CourseModality.EAD)

        manifest = {
            "courses": [_make_manifest_entry(code, nr) for code, nr in COURSE_CODES],
            "deactivate_codes": [],
        }

        async with AsyncSessionLocal() as db:
            await reconcile_regulatory_course_fields(db, WR_TENANT_ID, manifest, dry_run=False)
            await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
            await db.commit()

            result = await db.execute(
                select(CourseComplianceProfile)
                .join(Course, Course.id == CourseComplianceProfile.course_id)
                .where(CourseComplianceProfile.tenant_id == WR_TENANT_ID)
            )
            profiles = result.scalars().all()

        assert len(profiles) == 14

        profiles_by_code = {}
        async with AsyncSessionLocal() as db:
            for code, _ in COURSE_CODES:
                p = await _get_profile(WR_TENANT_ID, code)
                profiles_by_code[code] = p

        # NR-18-F must be REVIEW_REQUIRED
        assert profiles_by_code["NR-18-F"].status == ComplianceStatus.REVIEW_REQUIRED
        assert profiles_by_code["NR-18-F"].workload_source == WorkloadSource.REVIEW_REQUIRED

        # All others must be DRAFT (not APPROVED)
        for code, _ in COURSE_CODES:
            if code == "NR-18-F":
                continue
            p = profiles_by_code[code]
            assert p is not None, f"Missing profile for {code}"
            assert p.status == ComplianceStatus.DRAFT, f"{code} should be DRAFT, got {p.status}"
            assert p.technical_responsible_id is None, f"{code} should have NULL technical_responsible_id"

        # Verify Course field alignment for NORMATIVE_MINIMUM courses
        nr33_sup = await _get_course(WR_TENANT_ID, "NR-33-SUP")
        assert nr33_sup.carga_horaria == 40
        assert nr33_sup.modality == CourseModality.PRESENCIAL

        nr33_aut = await _get_course(WR_TENANT_ID, "NR-33-AUT")
        assert nr33_aut.carga_horaria == 16
        assert nr33_aut.modality == CourseModality.PRESENCIAL

        nr35_f = await _get_course(WR_TENANT_ID, "NR-35-F")
        assert nr35_f.carga_horaria == 8
        assert nr35_f.modality == CourseModality.PRESENCIAL

        nr10_b = await _get_course(WR_TENANT_ID, "NR-10-B")
        assert nr10_b.carga_horaria == 40

        # NR-06-F employer-defined — workload NOT converted
        nr06_f = await _get_course(WR_TENANT_ID, "NR-06-F")
        assert nr06_f.carga_horaria == 8  # was created with 8, not converted to normative

        # NR-18-F — Course NOT modified
        nr18_f = await _get_course(WR_TENANT_ID, "NR-18-F")
        assert nr18_f.carga_horaria == 8  # unchanged
        assert nr18_f.modality == CourseModality.EAD  # unchanged
    finally:
        await _cleanup_tenant(WR_TENANT_ID)


# ---------------------------------------------------------------------------
# Section 8 — Dry-run report format
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dry_run_report_format():
    """Dry-run report must include code, field, before, after, source, reason, action."""
    await _make_tenant(WR_TENANT_ID, "wr-dry", "WR Dry")
    try:
        await _make_course(WR_TENANT_ID, "NR-33-SUP", "NR-33", 16, CourseModality.SEMIPRESENCIAL)
        manifest = {"courses": [_make_manifest_entry("NR-33-SUP", "NR-33")], "deactivate_codes": []}

        async with AsyncSessionLocal() as db:
            report = await reconcile_regulatory_course_fields(db, WR_TENANT_ID, manifest, dry_run=True)
            await db.commit()

        updates = report["COURSE_FIELD_UPDATES"]
        assert len(updates) == 2  # carga_horaria + modality

        for item in updates:
            assert "code" in item
            assert "field" in item
            assert "before" in item
            assert "after" in item
            assert "source" in item
            assert "reason" in item
            assert "action" in item

        fields = {item["field"] for item in updates}
        assert "carga_horaria" in fields
        assert "modality" in fields

        ch_update = next(u for u in updates if u["field"] == "carga_horaria")
        assert ch_update["before"] == 16
        assert ch_update["after"] == 40
        assert ch_update["source"] == "NORMATIVE_MINIMUM"

        mod_update = next(u for u in updates if u["field"] == "modality")
        assert mod_update["before"] == "SEMIPRESENCIAL"
        assert mod_update["after"] == "PRESENCIAL"
        assert mod_update["source"] == "REGULATORY_WORKLOAD"

        # Course NOT modified in dry-run
        course = await _get_course(WR_TENANT_ID, "NR-33-SUP")
        assert course.carga_horaria == 16
        assert course.modality == CourseModality.SEMIPRESENCIAL
    finally:
        await _cleanup_tenant(WR_TENANT_ID)
