"""Integration test: regulatory matrix persistence to CourseComplianceProfile.

This test verifies that the REGULATORY_WORKLOAD map is actually persisted
to the database via upsert_regulatory_compliance_profile — not just
defined as a Python constant.

Flow:
1. Use the test database (with tables created by conftest setup_db).
2. Create a WR tenant.
3. Create courses with the 14 priority codes.
4. Run reconcile_regulatory_compliance.
5. Query CourseComplianceProfile from the database.
6. Assert the persisted fields match the expected regulatory rules.

This tests the DATABASE RECORDS, not the Python constants.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.compliance import ComplianceStatus, CourseComplianceProfile, WorkloadSource
from app.models.course import Course, CourseModality, CourseType
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User, UserRole
from app.scripts.import_wr_catalog import reconcile_regulatory_compliance

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


@pytest.fixture
async def wr_tenant_with_courses():
    """Create WR tenant + 14 priority courses in the test DB."""
    async with AsyncSessionLocal() as db:
        # Create WR tenant
        tenant = Tenant(
            id=WR_TENANT_ID,
            name="WR Consultoria Test Reg",
            slug="wr-test-reg",
            status=TenantStatus.ACTIVE,
            contact_name="Test",
            contact_email="test-reg@wr.com",
        )
        db.add(tenant)
        await db.flush()

        # Create admin user for class responsible
        admin = User(
            tenant_id=WR_TENANT_ID,
            email="admin@wr.com",
            full_name="Admin",
            role=UserRole.ADMIN,
            is_active=True,
            password_hash="x",
        )
        db.add(admin)
        await db.flush()

        # Create courses
        for code, nr_family in COURSE_CODES:
            course = Course(
                tenant_id=WR_TENANT_ID,
                code=code,
                name=f"Test {code}",
                category=f"NR {nr_family.split('-')[1]}",
                carga_horaria=8,
                modality=CourseModality.EAD,
                tipo_curso=CourseType.FORMACAO,
                price=100.0,
                is_active=True,
            )
            db.add(course)

        await db.commit()

    yield WR_TENANT_ID

    # Cleanup
    async with AsyncSessionLocal() as db:
        from sqlalchemy import delete

        await db.execute(delete(CourseComplianceProfile).where(CourseComplianceProfile.tenant_id == WR_TENANT_ID))
        await db.execute(delete(Course).where(Course.tenant_id == WR_TENANT_ID))
        await db.execute(delete(User).where(User.tenant_id == WR_TENANT_ID))
        await db.execute(delete(Tenant).where(Tenant.id == WR_TENANT_ID))
        await db.commit()


@pytest.mark.asyncio
async def test_regulatory_matrix_persisted_for_all_14_courses(wr_tenant_with_courses):
    """All 14 priority courses must have a CourseComplianceProfile after reconciliation."""
    manifest = {
        "courses": [_make_manifest_entry(code, nr) for code, nr in COURSE_CODES],
        "deactivate_codes": [],
    }

    async with AsyncSessionLocal() as db:
        await reconcile_regulatory_compliance(
            db, WR_TENANT_ID, manifest, dry_run=False
        )
        await db.commit()

        # Query all profiles from the database
        result = await db.execute(
            select(CourseComplianceProfile)
            .join(Course, Course.id == CourseComplianceProfile.course_id)
            .where(CourseComplianceProfile.tenant_id == WR_TENANT_ID)
        )
        profiles = result.scalars().all()

    assert len(profiles) == 14, f"Expected 14 profiles, got {len(profiles)}"


@pytest.mark.asyncio
async def test_nr10_b_regulatory_profile(wr_tenant_with_courses):
    """NR-10-B: NORMATIVE_MINIMUM, 2400 minutes, no practical component required."""
    manifest = {"courses": [_make_manifest_entry("NR-10-B", "NR-10")], "deactivate_codes": []}

    async with AsyncSessionLocal() as db:
        await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
        await db.commit()

        result = await db.execute(
            select(CourseComplianceProfile)
            .join(Course, Course.id == CourseComplianceProfile.course_id)
            .where(Course.tenant_id == WR_TENANT_ID, Course.code == "NR-10-B")
        )
        profile = result.scalar_one()

    assert profile.workload_source == WorkloadSource.NORMATIVE_MINIMUM
    assert profile.workload_minutes == 2400
    assert profile.normative_minimum_minutes == 2400


@pytest.mark.asyncio
async def test_nr10_s_regulatory_profile(wr_tenant_with_courses):
    """NR-10-S: NORMATIVE_MINIMUM, 2400 minutes, prerequisite NR-10-B."""
    manifest = {"courses": [_make_manifest_entry("NR-10-S", "NR-10")], "deactivate_codes": []}

    async with AsyncSessionLocal() as db:
        await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
        await db.commit()

        result = await db.execute(
            select(CourseComplianceProfile)
            .join(Course, Course.id == CourseComplianceProfile.course_id)
            .where(Course.tenant_id == WR_TENANT_ID, Course.code == "NR-10-S")
        )
        profile = result.scalar_one()

    assert profile.workload_source == WorkloadSource.NORMATIVE_MINIMUM
    assert profile.workload_minutes == 2400
    assert profile.normative_minimum_minutes == 2400
    assert profile.prerequisites is not None
    assert "NR-10-B" in profile.prerequisites


@pytest.mark.asyncio
async def test_nr06_f_regulatory_profile(wr_tenant_with_courses):
    """NR-06-F: EMPLOYER_DEFINED, no normative minimum."""
    manifest = {"courses": [_make_manifest_entry("NR-06-F", "NR-06")], "deactivate_codes": []}

    async with AsyncSessionLocal() as db:
        await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
        await db.commit()

        result = await db.execute(
            select(CourseComplianceProfile)
            .join(Course, Course.id == CourseComplianceProfile.course_id)
            .where(Course.tenant_id == WR_TENANT_ID, Course.code == "NR-06-F")
        )
        profile = result.scalar_one()

    assert profile.workload_source == WorkloadSource.EMPLOYER_DEFINED
    assert profile.normative_minimum_minutes is None


@pytest.mark.asyncio
async def test_nr12_f_regulatory_profile(wr_tenant_with_courses):
    """NR-12-F: PLH_DEFINED, no normative minimum, practical component required."""
    manifest = {"courses": [_make_manifest_entry("NR-12-F", "NR-12")], "deactivate_codes": []}

    async with AsyncSessionLocal() as db:
        await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
        await db.commit()

        result = await db.execute(
            select(CourseComplianceProfile)
            .join(Course, Course.id == CourseComplianceProfile.course_id)
            .where(Course.tenant_id == WR_TENANT_ID, Course.code == "NR-12-F")
        )
        profile = result.scalar_one()

    assert profile.workload_source == WorkloadSource.PLH_DEFINED
    assert profile.normative_minimum_minutes is None
    assert profile.requires_practical_component is True


@pytest.mark.asyncio
async def test_nr18_f_regulatory_profile(wr_tenant_with_courses):
    """NR-18-F: REVIEW_REQUIRED status — not promoted to Básico by inference."""
    manifest = {"courses": [_make_manifest_entry("NR-18-F", "NR-18")], "deactivate_codes": []}

    async with AsyncSessionLocal() as db:
        await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
        await db.commit()

        result = await db.execute(
            select(CourseComplianceProfile)
            .join(Course, Course.id == CourseComplianceProfile.course_id)
            .where(Course.tenant_id == WR_TENANT_ID, Course.code == "NR-18-F")
        )
        profile = result.scalar_one()

    assert profile.status == ComplianceStatus.REVIEW_REQUIRED
    assert profile.workload_source == WorkloadSource.REVIEW_REQUIRED
    assert profile.normative_minimum_minutes is None


@pytest.mark.asyncio
async def test_nr33_aut_regulatory_profile(wr_tenant_with_courses):
    """NR-33-AUT: PRESENCIAL, practical component, 12 months validity."""
    manifest = {"courses": [_make_manifest_entry("NR-33-AUT", "NR-33")], "deactivate_codes": []}

    async with AsyncSessionLocal() as db:
        await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
        await db.commit()

        result = await db.execute(
            select(CourseComplianceProfile)
            .join(Course, Course.id == CourseComplianceProfile.course_id)
            .where(Course.tenant_id == WR_TENANT_ID, Course.code == "NR-33-AUT")
        )
        profile = result.scalar_one()

    assert profile.delivery_mode == "PRESENCIAL"
    assert profile.requires_practical_component is True
    assert profile.validity_period_months == 12
    assert profile.workload_source == WorkloadSource.NORMATIVE_MINIMUM
    assert profile.normative_minimum_minutes == 960  # 16h * 60


@pytest.mark.asyncio
async def test_nr33_sup_regulatory_profile(wr_tenant_with_courses):
    """NR-33-SUP: PRESENCIAL, practical component, 12 months, 2400 min normative."""
    manifest = {"courses": [_make_manifest_entry("NR-33-SUP", "NR-33")], "deactivate_codes": []}

    async with AsyncSessionLocal() as db:
        await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
        await db.commit()

        result = await db.execute(
            select(CourseComplianceProfile)
            .join(Course, Course.id == CourseComplianceProfile.course_id)
            .where(Course.tenant_id == WR_TENANT_ID, Course.code == "NR-33-SUP")
        )
        profile = result.scalar_one()

    assert profile.delivery_mode == "PRESENCIAL"
    assert profile.requires_practical_component is True
    assert profile.validity_period_months == 12
    assert profile.workload_source == WorkloadSource.NORMATIVE_MINIMUM
    assert profile.normative_minimum_minutes == 2400  # 40h * 60


@pytest.mark.asyncio
async def test_nr35_f_regulatory_profile(wr_tenant_with_courses):
    """NR-35-F: PRESENCIAL, practical component, 24 months, 480 min normative."""
    manifest = {"courses": [_make_manifest_entry("NR-35-F", "NR-35")], "deactivate_codes": []}

    async with AsyncSessionLocal() as db:
        await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
        await db.commit()

        result = await db.execute(
            select(CourseComplianceProfile)
            .join(Course, Course.id == CourseComplianceProfile.course_id)
            .where(Course.tenant_id == WR_TENANT_ID, Course.code == "NR-35-F")
        )
        profile = result.scalar_one()

    assert profile.delivery_mode == "PRESENCIAL"
    assert profile.requires_practical_component is True
    assert profile.validity_period_months == 24
    assert profile.workload_source == WorkloadSource.NORMATIVE_MINIMUM
    assert profile.normative_minimum_minutes == 480  # 8h * 60


@pytest.mark.asyncio
async def test_nr11_variants_employer_defined(wr_tenant_with_courses):
    """All NR-11 variants: EMPLOYER_DEFINED, no normative minimum, practical required."""
    codes = ["NR-11-EMP", "NR-11-GUI", "NR-11-MIN", "NR-11-PLA", "NR-11-PON", "NR-11-RET"]
    manifest = {
        "courses": [_make_manifest_entry(c, "NR-11") for c in codes],
        "deactivate_codes": [],
    }

    async with AsyncSessionLocal() as db:
        await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
        await db.commit()

        for code in codes:
            result = await db.execute(
                select(CourseComplianceProfile)
                .join(Course, Course.id == CourseComplianceProfile.course_id)
                .where(Course.tenant_id == WR_TENANT_ID, Course.code == code)
            )
            profile = result.scalar_one_or_none()
            assert profile is not None, f"No profile for {code}"
            assert profile.workload_source == WorkloadSource.EMPLOYER_DEFINED
            assert profile.normative_minimum_minutes is None
            assert profile.requires_practical_component is True


@pytest.mark.asyncio
async def test_regulatory_upsert_is_idempotent(wr_tenant_with_courses):
    """Running reconcile twice must not duplicate or corrupt profiles."""
    manifest = {"courses": [_make_manifest_entry("NR-10-B", "NR-10")], "deactivate_codes": []}

    async with AsyncSessionLocal() as db:
        await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
        await db.commit()

        # Run again
        await reconcile_regulatory_compliance(db, WR_TENANT_ID, manifest, dry_run=False)
        await db.commit()

        result = await db.execute(
            select(CourseComplianceProfile)
            .join(Course, Course.id == CourseComplianceProfile.course_id)
            .where(Course.tenant_id == WR_TENANT_ID, Course.code == "NR-10-B")
        )
        profiles = result.scalars().all()

    assert len(profiles) == 1, "Idempotent upsert must not duplicate profiles"
    assert profiles[0].workload_source == WorkloadSource.NORMATIVE_MINIMUM
    assert profiles[0].workload_minutes == 2400
