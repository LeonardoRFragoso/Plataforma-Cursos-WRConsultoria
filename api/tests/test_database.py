import pytest
from sqlalchemy.exc import IntegrityError

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal, get_db_privileged
from app.models.user import User, UserRole


@pytest.mark.asyncio
async def test_get_db_privileged_sets_tenant_context():
    async for session in get_db_privileged():
        assert session.info["tenant_id"] == WR_TENANT_ID


@pytest.mark.asyncio
async def test_set_tenant_on_flush_requires_tenant_id():
    async with AsyncSessionLocal() as session:
        session.info["tenant_id"] = None
        user = User(
            email="missing@tenant.test",
            full_name="Missing Tenant",
            role=UserRole.STUDENT,
        )
        session.add(user)
        with pytest.raises(IntegrityError):
            await session.flush()
