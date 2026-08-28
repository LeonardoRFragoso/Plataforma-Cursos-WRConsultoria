"""B2B service-to-service authentication.

Central WR authenticates to the LMS via client_id + client_secret.
This module provides FastAPI dependencies that validate B2B
credentials, enforce scope-based access control, and ensure the
database session used by B2B routes has the correct RLS tenant
context.

Key design decisions:
- ``b2b_clients`` table lookup uses a PRIVILEGED session (bypass RLS)
  because the tenant is not known until the client is authenticated.
  See ``docs/CENTRAL_WR_B2B_API.md`` for the rationale.
- After authentication, a NEW session is created with
  ``set_config('app.current_tenant', :tid, true)`` using a
  parameterized query (no string interpolation).
- Missing headers return 401 (not 422) to avoid leaking whether
  the client_id exists.
- The error message is identical for all auth failures.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import WR_TENANT_ID
from app.core.context import current_tenant_id
from app.core.database import AsyncSessionLocal
from app.core.security import verify_password
from app.models.b2b_client import B2BClient

_AUTH_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid B2B client credentials",
    headers={"WWW-Authenticate": "B2B"},
)


@dataclass
class B2BContext:
    """Authenticated B2B context — carries tenant_id and scopes.

    Created once per request by ``get_b2b_context`` and cached by
    FastAPI's dependency injection cache.
    """

    client: B2BClient
    tenant_id: UUID
    scopes: set[str]


async def get_b2b_context(
    x_b2b_client_id: str | None = Header(None, alias="X-B2B-Client-Id"),
    x_b2b_client_secret: str | None = Header(None, alias="X-B2B-Client-Secret"),
) -> B2BContext:
    """Authenticate B2B client and return context with tenant_id + scopes.

    Uses a privileged session (bypass RLS) to look up the client record,
    because the tenant is unknown until authentication succeeds.

    Raises 401 for:
    - Missing client_id header
    - Missing client_secret header
    - Non-existent client_id
    - Wrong secret
    - Inactive client

    The error message is identical in all cases to avoid leaking
    whether a client_id exists.
    """
    if not x_b2b_client_id or not x_b2b_client_secret:
        raise _AUTH_ERROR

    # Privileged session — bypass RLS for client lookup.
    # The b2b_clients table is NOT RLS-protected because we need to
    # look up the client by client_id before knowing the tenant.
    # See docs/CENTRAL_WR_B2B_API.md § "b2b_clients RLS exemption".
    async with AsyncSessionLocal() as session:
        session.info["tenant_id"] = WR_TENANT_ID
        await session.execute(
            text("SELECT set_config('app.current_tenant', :tid, true)"),
            {"tid": str(WR_TENANT_ID)},
        )
        await session.execute(text("SET LOCAL app.bypass_rls = '1'"))

        client = await session.scalar(
            select(B2BClient).where(
                B2BClient.client_id == x_b2b_client_id,
                B2BClient.is_active.is_(True),
            )
        )
        if client is None:
            raise _AUTH_ERROR
        if not verify_password(x_b2b_client_secret, client.client_secret_hash):
            raise _AUTH_ERROR

        scopes = {s.strip() for s in client.allowed_scopes.split(",") if s.strip()}
        return B2BContext(client=client, tenant_id=client.tenant_id, scopes=scopes)


async def get_b2b_db(ctx: B2BContext = Depends(get_b2b_context)) -> AsyncSession:
    """Database session with RLS scoped to the B2B client's tenant.

    This is the ONLY db dependency B2B routes should use. It guarantees:
    - ``app.current_tenant`` is set to the client's tenant_id
    - RLS policies filter all queries to that tenant
    - The ContextVar is kept consistent
    - No string interpolation in SQL (uses ``set_config`` with params)
    """
    async with AsyncSessionLocal() as session:
        session.info["tenant_id"] = ctx.tenant_id
        await session.execute(
            text("SELECT set_config('app.current_tenant', :tid, true)"),
            {"tid": str(ctx.tenant_id)},
        )
        current_tenant_id.set(ctx.tenant_id)
        yield session


def require_b2b_scope(*scopes: str):
    """Dependency factory that checks the B2B client has one of the scopes.

    Usage::

        @router.get("/courses", dependencies=[Depends(require_b2b_scope("courses:read", "academic:read"))])

    ``academic:read`` is a superset scope that grants access to all
    academic endpoints. Specific scopes (``courses:read``, etc.) grant
    access only to their respective endpoints.
    """

    async def dependency(ctx: B2BContext = Depends(get_b2b_context)) -> B2BContext:
        # academic:read is a superset — if the client has it, all
        # academic scopes are satisfied.
        if "academic:read" in ctx.scopes:
            return ctx
        if not any(scope in ctx.scopes for scope in scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="B2B client lacks required scope",
            )
        return ctx

    return dependency
