from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.core.config import settings
from app.core.constants import WR_TENANT_ID
from app.core.context import current_tenant_id

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


def _resolve_tenant_id() -> str:
    tenant_id = current_tenant_id.get()
    if tenant_id:
        return str(tenant_id)
    return str(WR_TENANT_ID)


async def get_db():
    tenant_id = _resolve_tenant_id()
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(f"SET LOCAL app.current_tenant = '{tenant_id}'")
        )
        yield session
