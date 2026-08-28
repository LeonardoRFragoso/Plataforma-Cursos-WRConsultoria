"""B2B service-to-service authentication.

Central WR authenticates to the LMS via client_id + client_secret.
This module provides the FastAPI dependency that validates B2B
credentials and enforces scope-based access control.

Unlike user JWT auth, B2B auth:
- Uses a separate credential set (not JWT, not SSO secret)
- Is tenant-scoped (the client is bound to one LMS tenant)
- Enforces read-only scopes (academic:read, courses:read, etc.)
- Bypasses the normal user-based RLS by setting the tenant context
  directly from the B2B client's tenant_id
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import current_tenant_id
from app.core.database import get_db
from app.core.security import verify_password
from app.models.b2b_client import B2BClient


async def get_b2b_client(
    x_b2b_client_id: str = Header(..., alias="X-B2B-Client-Id"),
    x_b2b_client_secret: str = Header(..., alias="X-B2B-Client-Secret"),
    db: AsyncSession = Depends(get_db),
) -> B2BClient:
    """Validate B2B client credentials and return the client record.

    Raises 401 for invalid credentials, 403 for inactive clients.
    Sets the tenant context so RLS filters data to the client's tenant.
    """
    client = await db.scalar(
        select(B2BClient).where(
            B2BClient.client_id == x_b2b_client_id,
            B2BClient.is_active.is_(True),
        )
    )
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid B2B client credentials",
        )
    if not verify_password(x_b2b_client_secret, client.client_secret_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid B2B client credentials",
        )
    # Set tenant context for RLS — B2B queries are scoped to the
    # client's registered tenant, regardless of any header.
    current_tenant_id.set(client.tenant_id)
    return client


def require_b2b_scope(*scopes: str):
    """Dependency factory that checks the B2B client has one of the scopes.

    Usage::

        @router.get("/courses", dependencies=[Depends(require_b2b_scope("courses:read", "academic:read"))])
    """

    async def dependency(client: B2BClient = Depends(get_b2b_client)) -> B2BClient:
        client_scopes = {s.strip() for s in client.allowed_scopes.split(",") if s.strip()}
        if not any(scope in client_scopes for scope in scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"B2B client lacks required scope: {', '.join(scopes)}",
            )
        return client

    return dependency
