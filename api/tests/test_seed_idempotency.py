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

    # Set all except student password
    env = _seed_env()
    del env["DEMO_WR_STUDENT_PASSWORD"]
    for k, v in env.items():
        os.environ[k] = v
    os.environ.pop("DEMO_WR_STUDENT_PASSWORD", None)

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
