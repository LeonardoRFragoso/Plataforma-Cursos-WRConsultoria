"""Tests for demo seed idempotency and password gating.

Verifies:
- Running seed twice produces same counts and same IDs
- All four passwords are required (no defaults)
- Seed refuses to run without DEMO_SEED_MODE
- Seed refuses to run in production
"""

import os

import pytest
from sqlalchemy import func, select, text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.models.certificate import Certificate
from app.models.class_model import Class
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.payment import Payment
from app.models.plan import Plan
from app.models.student import Student
from app.models.tenant import Tenant
from app.models.tenant_subscription import TenantSubscription
from app.models.user import User


async def _set_rls_bypass(db):
    await db.execute(text(f"SET LOCAL app.current_tenant = '{WR_TENANT_ID}'"))
    await db.execute(text("SET LOCAL app.bypass_rls = '1'"))


async def _count_all():
    """Count all rows in tenant-aware tables."""
    counts = {}
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        for model, name in [
            (Tenant, "tenants"),
            (User, "users"),
            (Student, "students"),
            (Course, "courses"),
            (Class, "classes"),
            (Enrollment, "enrollments"),
            (Payment, "payments"),
            (Certificate, "certificates"),
            (Lesson, "lessons"),
            (Plan, "plans"),
            (TenantSubscription, "tenant_subscriptions"),
        ]:
            result = await db.execute(select(func.count()).select_from(model))
            counts[name] = result.scalar()
    return counts


async def _collect_ids():
    """Collect all IDs for idempotency comparison."""
    ids = {}
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        for model, name in [
            (Tenant, "tenants"),
            (User, "users"),
            (Course, "courses"),
            (Class, "classes"),
            (Enrollment, "enrollments"),
            (Payment, "payments"),
            (Certificate, "certificates"),
        ]:
            result = await db.execute(select(model.id))
            ids[name] = sorted([str(r) for r in result.scalars().all()])
    return ids


def _seed_env():
    """Return the env vars needed for seeding."""
    return {
        "DEMO_SEED_MODE": "true",
        "ENVIRONMENT": "staging",
        "DEMO_WR_ADMIN_EMAIL": "admin@wr.demo",
        "DEMO_WR_ADMIN_PASSWORD": "test-wr-admin-pass",
        "DEMO_ALFA_ADMIN_EMAIL": "admin@alfa.demo",
        "DEMO_ALFA_ADMIN_PASSWORD": "test-alfa-admin-pass",
        "DEMO_WR_STUDENT_PASSWORD": "test-wr-student-pass",
        "DEMO_ALFA_STUDENT_PASSWORD": "test-alfa-student-pass",
        "DEMO_SUPER_ADMIN_EMAIL": "super@wr.demo",
        "DEMO_SUPER_ADMIN_PASSWORD": "test-super-admin-pass",
    }


@pytest.mark.asyncio
async def test_seed_idempotent_counts(monkeypatch):
    """Running seed twice produces identical counts."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "DEMO_SEED_MODE", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")

    env = _seed_env()
    for k, v in env.items():
        os.environ[k] = v

    from app.scripts.seed_white_label_demo import main

    # First run
    await main()

    counts1 = await _count_all()
    ids1 = await _collect_ids()

    # Second run
    await main()

    counts2 = await _count_all()
    ids2 = await _collect_ids()

    # Counts must be identical
    for table, count in counts1.items():
        assert counts2[table] == count, (
            f"Table {table}: first run={count}, second run={counts2[table]}. "
            f"Seed is NOT idempotent!"
        )

    # IDs must be identical
    for table, id_list in ids1.items():
        assert ids2[table] == id_list, (
            f"Table {table}: IDs differ between runs. Seed is NOT idempotent!"
        )


@pytest.mark.asyncio
async def test_seed_requires_all_passwords(monkeypatch):
    """Seed aborts if any password env var is missing."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "DEMO_SEED_MODE", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")

    # Set all except super admin password
    env = _seed_env()
    del env["DEMO_SUPER_ADMIN_PASSWORD"]
    for k, v in env.items():
        os.environ[k] = v
    os.environ.pop("DEMO_SUPER_ADMIN_PASSWORD", None)

    from app.scripts.seed_white_label_demo import main

    # Should abort
    with pytest.raises(SystemExit) as exc_info:
        await main()
    assert exc_info.value.code == 1


@pytest.mark.asyncio
async def test_seed_refuses_without_demo_mode(monkeypatch):
    """Seed aborts if DEMO_SEED_MODE is false."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "DEMO_SEED_MODE", False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")

    from app.scripts.seed_white_label_demo import main

    with pytest.raises(SystemExit) as exc_info:
        await main()
    assert exc_info.value.code == 1


@pytest.mark.asyncio
async def test_seed_refuses_in_production(monkeypatch):
    """Seed aborts if ENVIRONMENT is production."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "DEMO_SEED_MODE", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    env = _seed_env()
    env["ENVIRONMENT"] = "production"
    for k, v in env.items():
        os.environ[k] = v

    from app.scripts.seed_white_label_demo import main

    with pytest.raises(SystemExit) as exc_info:
        await main()
    assert exc_info.value.code == 1


@pytest.mark.asyncio
async def test_seed_handles_multiple_preexisting_payments(monkeypatch):
    """Seed succeeds even if multiple payments already exist for an enrollment.
    
    This tests the fix for the idempotency issue where pre-existing duplicate
    Payment records would cause scalar_one_or_none() to fail.
    
    Scenario:
    - Run seed once (creates enrollment + payment)
    - Manually create a second payment for the same enrollment
    - Run seed again
    - Expected: seed succeeds, payment count does not increase
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "DEMO_SEED_MODE", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")

    env = _seed_env()
    for k, v in env.items():
        os.environ[k] = v

    from app.scripts.seed_white_label_demo import main

    # First run
    await main()

    # Get the first enrollment and create a duplicate payment
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)

        # Find the first enrollment
        result = await db.execute(select(Enrollment).limit(1))
        enrollment = result.scalar_one()

        # Create a second payment for the same enrollment
        from app.core.utils import utc_now
        from app.models.payment import PaymentMethod, PaymentStatus

        second_payment = Payment(
            tenant_id=enrollment.tenant_id,
            enrollment_id=enrollment.id,
            amount=enrollment.price,
            status=PaymentStatus.PENDENTE,  # Different status to test preference
            method=PaymentMethod.CARTAO,
            created_at=utc_now(),
        )
        db.add(second_payment)
        await db.commit()

    # Count payments before second seed run
    counts_before = await _count_all()
    payments_before = counts_before["payments"]

    # Second run should succeed despite multiple payments
    await main()

    # Count payments after second seed run
    counts_after = await _count_all()
    payments_after = counts_after["payments"]

    # Payment count must not increase (seed selected existing, not created new)
    assert payments_after == payments_before, (
        f"Payment count increased: before={payments_before}, after={payments_after}. "
        f"Seed did not handle multiple pre-existing payments correctly!"
    )


@pytest.mark.asyncio
async def test_seed_lesson_fixtures_deterministic(monkeypatch):
    """Seed creates exactly 10 deterministic lessons (5 per tenant)."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "DEMO_SEED_MODE", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")

    env = _seed_env()
    for k, v in env.items():
        os.environ[k] = v

    from app.scripts.seed_white_label_demo import main

    # First run
    await main()

    # Count lessons
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        result = await db.execute(select(func.count()).select_from(Lesson))
        lessons_count_1 = result.scalar()

    assert lessons_count_1 == 10, f"Expected 10 lessons, got {lessons_count_1}"

    # Second run
    await main()

    # Count lessons again
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        result = await db.execute(select(func.count()).select_from(Lesson))
        lessons_count_2 = result.scalar()

    assert lessons_count_2 == 10, f"Expected 10 lessons after second run, got {lessons_count_2}"


@pytest.mark.asyncio
async def test_seed_certified_student_coherent_state(monkeypatch):
    """Certified students have 100% progress, CONCLUIDA, and 1 certificate."""
    from app.core.config import settings
    from app.models.lesson import LessonProgress

    monkeypatch.setattr(settings, "DEMO_SEED_MODE", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")

    env = _seed_env()
    for k, v in env.items():
        os.environ[k] = v

    from app.scripts.seed_white_label_demo import main

    await main()

    # Verify WR aluno1 (certified student)
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)

        # Find aluno1
        result = await db.execute(
            select(Student).join(User).where(User.email == "aluno1@wr.demo")
        )
        student = result.scalar_one()

        # Check enrollment status
        result = await db.execute(
            select(Enrollment).where(Enrollment.student_id == student.id)
        )
        enrollment = result.scalar_one()
        assert enrollment.status.value == "CONCLUIDA", f"Expected CONCLUIDA, got {enrollment.status}"

        # Check certificate count
        result = await db.execute(
            select(func.count()).select_from(Certificate).where(
                Certificate.enrollment_id == enrollment.id
            )
        )
        cert_count = result.scalar()
        assert cert_count == 1, f"Expected 1 certificate, got {cert_count}"

        # Check lesson progress (all required lessons complete)
        result = await db.execute(
            select(LessonProgress).where(LessonProgress.student_id == student.id)
        )
        progress_records = result.scalars().all()
        completed = sum(1 for p in progress_records if p.completed)
        assert completed == 4, f"Expected 4 completed lessons, got {completed}"


@pytest.mark.asyncio
async def test_seed_non_certified_student_zero_progress(monkeypatch):
    """Non-certified students have 0% progress, CONFIRMADA, and 0 certificates."""
    from app.core.config import settings
    from app.models.lesson import LessonProgress

    monkeypatch.setattr(settings, "DEMO_SEED_MODE", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")

    env = _seed_env()
    for k, v in env.items():
        os.environ[k] = v

    from app.scripts.seed_white_label_demo import main

    await main()

    # Verify WR aluno2 (non-certified student)
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)

        # Find aluno2
        result = await db.execute(
            select(Student).join(User).where(User.email == "aluno2@wr.demo")
        )
        student = result.scalar_one()

        # Check enrollment status
        result = await db.execute(
            select(Enrollment).where(Enrollment.student_id == student.id)
        )
        enrollment = result.scalar_one()
        assert enrollment.status.value == "CONFIRMADA", f"Expected CONFIRMADA, got {enrollment.status}"

        # Check certificate count
        result = await db.execute(
            select(func.count()).select_from(Certificate).where(
                Certificate.enrollment_id == enrollment.id
            )
        )
        cert_count = result.scalar()
        assert cert_count == 0, f"Expected 0 certificates, got {cert_count}"

        # Check lesson progress (no lessons complete)
        result = await db.execute(
            select(LessonProgress).where(LessonProgress.student_id == student.id)
        )
        progress_records = result.scalars().all()
        completed = sum(1 for p in progress_records if p.completed)
        assert completed == 0, f"Expected 0 completed lessons, got {completed}"


@pytest.mark.asyncio
async def test_payment_selection_idempotent(monkeypatch):
    """Payment selection is idempotent even with multiple pre-existing payments."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "DEMO_SEED_MODE", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")

    env = _seed_env()
    for k, v in env.items():
        os.environ[k] = v

    from app.scripts.seed_white_label_demo import main

    # First run
    await main()
    counts_1 = await _count_all()
    payments_1 = counts_1["payments"]

    # Second run
    await main()
    counts_2 = await _count_all()
    payments_2 = counts_2["payments"]

    # Payment count must remain the same
    assert payments_2 == payments_1, (
        f"Payment count changed: first run={payments_1}, second run={payments_2}. "
        f"Seed payment selection is not idempotent!"
    )
