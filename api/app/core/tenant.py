"""Resolução de tenant por requisição e helpers de escopo."""

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import WR_TENANT_ID
from app.models.tenant import Tenant


class TenantResolver:
    """Resolve o tenant atual a partir do host/custom domain/header de teste.

    Ordem de resolução:

    1. Em dev/teste (ENVIRONMENT != production): header explícito
       ``X-Tenant-Id`` (UUID) para testes de isolamento automatizados.
    2. Header ``X-Tenant-Slug`` enviado por um frontend confiável
       (Origin em ``TRUSTED_FRONTEND_ORIGINS``). Em produção, origens não
       confiáveis são rejeitadas e o header é ignorado.
    3. Custom domain VERIFIED/ACTIVE casando com o Host da requisição.
    4. Slug derivado do Host (subdomínio) ou fallback WR.
    """

    def __init__(self) -> None:
        self.master_host = getattr(settings, "MASTER_HOST", "localhost")
        self.trusted_origins = {
            origin.strip().rstrip("/")
            for origin in getattr(settings, "TRUSTED_FRONTEND_ORIGINS", [])
            if origin and origin.strip()
        }

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

    def _is_trusted_origin(self, origin: str | None) -> bool:
        if not origin:
            return False
        return origin.strip().rstrip("/") in self.trusted_origins

    async def _resolve_by_slug(self, db: AsyncSession, slug: str) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.slug == slug)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def resolve(self, request: Request, db: AsyncSession) -> Tenant:
        host = request.headers.get("host", "")

        # 1. Em dev/teste, permite header explícito (UUID) para testes de
        #    isolamento automatizados. Nunca disponível em produção.
        test_tenant = request.headers.get("x-tenant-id")
        if test_tenant and not self._is_production():
            stmt = select(Tenant).where(Tenant.id == test_tenant)
            result = await db.execute(stmt)
            tenant = result.scalar_one_or_none()
            if tenant:
                return tenant

        # 2. Header X-Tenant-Slug enviado por frontend confiável.
        #    Em produção, exige Origin em TRUSTED_FRONTEND_ORIGINS.
        slug_header = request.headers.get("x-tenant-slug")
        if slug_header:
            slug_header = slug_header.strip().lower()
            if self._is_production():
                origin = request.headers.get("origin") or request.headers.get("referer")
                if not self._is_trusted_origin(origin):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Untrusted origin for tenant context",
                    )
            tenant = await self._resolve_by_slug(db, slug_header)
            if tenant:
                return tenant
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found",
            )

        # 3. Custom domain VERIFIED/ACTIVE.
        stmt = select(Tenant).where(
            Tenant.custom_domain == host,
            Tenant.custom_domain_status.in_(["VERIFIED", "ACTIVE"]),
        )
        result = await db.execute(stmt)
        tenant = result.scalar_one_or_none()
        if tenant:
            return tenant

        # 4. Slug derivado do Host ou fallback WR.
        slug = self._host_to_slug(host) or "wr"
        tenant = await self._resolve_by_slug(db, slug)
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
