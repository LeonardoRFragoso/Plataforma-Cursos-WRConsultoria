"""B2B service-to-service authentication.

Central WR authenticates to the LMS via client_id + client_secret.
This module provides FastAPI dependencies that validate B2B
credentials, enforce scope-based access control, and ensure the
database session used by B2B routes has the correct RLS tenant
context.

Key design decisions:
- ``b2b_clients`` table lookup does NOT use ``bypass_rls``. The table
  has no RLS policies (it is a global lookup table), so a plain
  session with ``app.current_tenant`` set to the WR tenant is
  sufficient. No privileged escalation is needed.
- After authentication, a NEW session is created with
  ``set_config('app.current_tenant', :tid, true)`` using a
  parameterized query (no string interpolation). This session has
  ``app.bypass_rls`` explicitly set to ``'0'`` (defense in depth).
- Subscription enforcement is applied AFTER B2B authentication,
  using the authenticated ``tenant_id`` — never the host-derived one.
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
from app.core.rate_limit import get_rate_limiter
from app.core.security import verify_password
from app.models.b2b_client import B2BClient
from app.models.tenant_subscription import TenantSubscription

_AUTH_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid B2B client credentials",
    headers={"WWW-Authenticate": "B2B"},
)

_SUBSCRIPTION_BLOCKED = HTTPException(
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    detail="LMS tenant temporarily unavailable for B2B access.",
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


async def _check_subscription(tenant_id: UUID) -> None:
    """Enforce subscription status AFTER B2B authentication.

    Uses the authenticated ``tenant_id`` (from the B2B client record),
    never the host-derived tenant. A SUSPENDED or CANCELLED tenant
    blocks B2B access with 503.
    """
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = tenant_id
        await db.execute(
            text("SELECT set_config('app.current_tenant', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        result = await db.execute(
            select(TenantSubscription)
            .where(TenantSubscription.tenant_id == tenant_id)
            .order_by(TenantSubscription.updated_at.desc())
            .limit(1)
        )
        sub = result.scalar_one_or_none()
        if sub and sub.status in ("SUSPENDED", "CANCELLED"):
            raise _SUBSCRIPTION_BLOCKED


async def get_b2b_context(
    x_b2b_client_id: str | None = Header(None, alias="X-B2B-Client-Id"),
    x_b2b_client_secret: str | None = Header(None, alias="X-B2B-Client-Secret"),
) -> B2BContext:
    """Authenticate B2B client and return context with tenant_id + scopes.

    The ``b2b_clients`` table has no RLS policies (it is a global
    lookup table), so no ``bypass_rls`` privilege is needed. We set
    ``app.current_tenant`` to the WR tenant for the lookup session
    (harmless — the table is not RLS-filtered).

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

    # Lookup session — b2b_clients has no RLS, so no bypass_rls needed.
    # We set current_tenant to WR_TENANT_ID for consistency but it has
    # no effect on the b2b_clients table (no policies exist on it).
    async with AsyncSessionLocal() as session:
        session.info["tenant_id"] = WR_TENANT_ID
        await session.execute(
            text("SELECT set_config('app.current_tenant', :tid, true)"),
            {"tid": str(WR_TENANT_ID)},
        )

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
        ctx = B2BContext(client=client, tenant_id=client.tenant_id, scopes=scopes)

    # Post-auth per-client rate limit — uses the AUTHENTICATED client.id,
    # not the presented X-B2B-Client-Id header. This prevents rotating
    # fake client IDs to obtain new quotas. The pre-auth IP limit in the
    # middleware still applies before this check.
    from app.core.config import settings
    if settings.RATE_LIMIT_ENABLED:
        backend = get_rate_limiter()
        client_key = f"b2b-auth-client:{ctx.client.client_id[:128]}"
        if not backend.is_allowed(
            client_key,
            settings.B2B_RATE_LIMIT_REQUESTS,
            settings.B2B_RATE_LIMIT_WINDOW_SECONDS,
        ):
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )

    # Enforce subscription AFTER authentication, using the authenticated
    # tenant_id — never the host-derived tenant.
    await _check_subscription(ctx.tenant_id)
    return ctx


async def get_b2b_db(ctx: B2BContext = Depends(get_b2b_context)) -> AsyncSession:
    """Database session with RLS scoped to the B2B client's tenant.

    This is the ONLY db dependency B2B routes should use. It guarantees:
    - ``app.current_tenant`` is set to the client's tenant_id
    - ``app.bypass_rls`` is explicitly set to ``'0'`` (defense in depth)
    - RLS policies filter all queries to that tenant
    - The ContextVar is kept consistent and **restored** after the
      request (via ``ContextVar.reset(token)``) to prevent leakage
      into subsequent requests.
    - No string interpolation in SQL (uses ``set_config`` with params)
    """
    token = current_tenant_id.set(ctx.tenant_id)
    try:
        async with AsyncSessionLocal() as session:
            session.info["tenant_id"] = ctx.tenant_id
            await session.execute(
                text("SELECT set_config('app.current_tenant', :tid, true)"),
                {"tid": str(ctx.tenant_id)},
            )
            # Explicitly ensure bypass_rls is OFF — defense in depth.
            await session.execute(text("SET LOCAL app.bypass_rls = '0'"))
            yield session
    finally:
        current_tenant_id.reset(token)


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
