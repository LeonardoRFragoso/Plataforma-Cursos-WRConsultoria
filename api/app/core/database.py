from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, declarative_base

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


@event.listens_for(Session, "before_flush")
def _set_tenant_on_flush(session, flush_context, instances):
    """Define tenant_id dos novos objetos a partir do contexto da sessão."""
    if "tenant_id" not in session.info:
        session.info["tenant_id"] = WR_TENANT_ID
    tenant_id = session.info["tenant_id"]
    for obj in session.new:
        if hasattr(obj, "tenant_id") and obj.tenant_id is None:
            if not tenant_id:
                raise IntegrityError(
                    "tenant_id required but no tenant resolved",
                    params=None,
                    orig=None,
                )
            obj.tenant_id = tenant_id


async def get_db():
    tenant_id = _resolve_tenant_id()
    resolved = current_tenant_id.get() or WR_TENANT_ID
    async with AsyncSessionLocal() as session:
        session.info["tenant_id"] = resolved
        await session.execute(
            text(f"SET LOCAL app.current_tenant = '{tenant_id}'")
        )
        yield session


async def get_db_privileged():
    """Sessão que desvia do RLS para operações globais do super_admin."""
    async with AsyncSessionLocal() as session:
        session.info["tenant_id"] = WR_TENANT_ID
        await session.execute(
            text(f"SET LOCAL app.current_tenant = '{WR_TENANT_ID}'")
        )
        await session.execute(text("SET LOCAL app.bypass_rls = '1'"))
        yield session
