"""Resolução de tenant por requisição e helpers de escopo."""

from urllib.parse import urlparse

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import WR_TENANT_ID
from app.models.tenant import Tenant

# Environments where X-Tenant-Id (test-only UUID header) is accepted.
# Staging and production must NEVER accept it.
_TEST_ONLY_ENVS = frozenset({"development", "dev", "test", "testing"})

# Environments that require trusted Origin for X-Tenant-Slug.
# Staging is publicly exposed and must enforce trust just like production.
_PUBLIC_ENVS = frozenset({"production", "staging"})


def _current_env() -> str:
    return getattr(settings, "ENVIRONMENT", "").lower()


def is_test_environment() -> bool:
    """True only in local dev / automated test environments."""
    return _current_env() in _TEST_ONLY_ENVS


def requires_trusted_tenant_context() -> bool:
    """True when the environment is publicly exposed and must enforce
    trusted Origin for X-Tenant-Slug.

    production → True
    staging    → True
    development/test → False (local/test behavior allowed)
    """
    return _current_env() in _PUBLIC_ENVS


class TenantResolver:
    """Resolve o tenant atual a partir do host/custom domain/header.

    Ordem de resolução:

    1. Em dev/teste APENAS (development, test, testing): header explícito
       ``X-Tenant-Id`` (UUID) para testes de isolamento automatizados.
       Nunca disponível em staging ou produção.
    2. Header ``X-Tenant-Slug`` enviado por um frontend confiável.
       Em staging E produção, exige Origin em ``TRUSTED_FRONTEND_ORIGINS``.
       Origens não confiáveis são rejeitadas (400).
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
        # Origin header is scheme://host:port (no path). Compare directly.
        origin_normalized = origin.strip().rstrip("/")
        if origin_normalized in self.trusted_origins:
            return True
        # Fallback: Referer may contain a full URL with path. Parse it
        # to extract just the origin (scheme://host:port).
        parsed = urlparse(origin_normalized)
        if parsed.scheme and parsed.netloc:
            reconstructed = f"{parsed.scheme}://{parsed.netloc}"
            if reconstructed in self.trusted_origins:
                return True
        return False

    def _extract_origin(self, request: Request) -> str | None:
        """Prefer Origin header; fall back to Referer parsed as origin."""
        origin = request.headers.get("origin")
        if origin:
            return origin
        referer = request.headers.get("referer")
        if referer:
            parsed = urlparse(referer)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"
        return None

    async def _resolve_by_slug(self, db: AsyncSession, slug: str) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.slug == slug)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def resolve(self, request: Request, db: AsyncSession) -> Tenant:
        host = request.headers.get("host", "")

        # 1. X-Tenant-Id (UUID) — ONLY in dev/test environments.
        #    Staging and production must NEVER accept this header.
        if is_test_environment():
            test_tenant = request.headers.get("x-tenant-id")
            if test_tenant:
                stmt = select(Tenant).where(Tenant.id == test_tenant)
                result = await db.execute(stmt)
                tenant = result.scalar_one_or_none()
                if tenant:
                    return tenant

        # 2. Header X-Tenant-Slug enviado por frontend confiável.
        #    Staging AND production require Origin in TRUSTED_FRONTEND_ORIGINS.
        slug_header = request.headers.get("x-tenant-slug")
        if slug_header:
            slug_header = slug_header.strip().lower()
            if requires_trusted_tenant_context():
                origin = self._extract_origin(request)
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


async def get_tenant_from_request(request: Request) -> Tenant:
    """Dependência para injetar tenant atual nas rotas protegidas."""
    tenant_id = request.state.get("tenant_id") if hasattr(request, "state") else None
    if tenant_id:
        return tenant_id
    return WR_TENANT_ID
