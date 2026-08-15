"""Resolução de tenant por requisição e helpers de escopo."""

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import WR_TENANT_ID
from app.models.tenant import Tenant


class TenantResolver:
    """Resolve o tenant atual a partir do host/custom domain/header de teste."""

    def __init__(self) -> None:
        self.master_host = getattr(settings, "MASTER_HOST", "localhost")

    def _host_to_slug(self, host: str | None) -> str | None:
        if not host:
            return None

        host = host.split(":")[0].lower()

        if "[" in host or "/" in host:
            return None

        if host in ("localhost", "127.0.0.1", self.master_host):
            return "wr"

        parts = host.split(".")
        if len(parts) >= 3:
            return parts[0]

        if len(parts) == 2:
            return "wr"

        return None

    async def resolve(self, request: Request, db: AsyncSession) -> Tenant:
        host = request.headers.get("host", "")

        # Em dev/testes, permite header explícito para testes de isolamento
        test_tenant = request.headers.get("x-tenant-id")
        if test_tenant and not self._is_production():
            stmt = select(Tenant).where(Tenant.id == test_tenant)
            result = await db.execute(stmt)
            tenant = result.scalar_one_or_none()
            if tenant:
                return tenant

        stmt = select(Tenant).where(Tenant.custom_domain == host)
        result = await db.execute(stmt)
        tenant = result.scalar_one_or_none()
        if tenant:
            return tenant

        slug = self._host_to_slug(host) or "wr"
        stmt = select(Tenant).where(Tenant.slug == slug)
        result = await db.execute(stmt)
        tenant = result.scalar_one_or_none()
        if tenant:
            return tenant

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    @staticmethod
    def _is_production() -> bool:
        return getattr(settings, "ENVIRONMENT", "").lower() == "production"


async def get_tenant_from_request(request: Request) -> Tenant:
    """Dependência para injetar tenant atual nas rotas protegidas."""
    tenant_id = request.state.get("tenant_id") if hasattr(request, "state") else None
    if tenant_id:
        return tenant_id
    return WR_TENANT_ID
