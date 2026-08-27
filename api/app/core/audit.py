"""Best-effort append-only audit trail for administrative mutations.

Only request metadata is recorded. Request/response bodies, query strings,
authorization headers and credentials are intentionally excluded.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import Request, Response
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.models.governance import AdminAuditLog

logger = logging.getLogger(__name__)
_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_ADMIN_ROLES = frozenset({"admin", "super_admin"})


class AdminAuditMiddleware(BaseHTTPMiddleware):
    """Persist metadata for authenticated admin mutations without affecting UX.

    Audit persistence is best-effort: a logging failure is reported to the
    structured application log but never changes the already-computed business
    response. Database constraints/RLS remain the authority for business data.
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if request.method.upper() not in _MUTATING_METHODS:
            return response

        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return response

        try:
            payload = decode_token(auth.split(" ", 1)[1].strip())
            role = str(payload.get("role") or "").lower()
            if role not in _ADMIN_ROLES:
                return response

            actor_raw = payload.get("sub")
            tenant_raw = getattr(request.state, "tenant_id", None) or payload.get("tenant_id")
            if not actor_raw or not tenant_raw:
                return response

            actor_id = UUID(str(actor_raw))
            tenant_id = UUID(str(tenant_raw))
            request_id = getattr(request.state, "request_id", None)

            async with AsyncSessionLocal() as db:
                db.info["tenant_id"] = tenant_id
                await db.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
                db.add(
                    AdminAuditLog(
                        tenant_id=tenant_id,
                        actor_id=actor_id,
                        actor_role=role,
                        method=request.method.upper(),
                        path=request.url.path[:512],
                        status_code=response.status_code,
                        request_id=str(request_id)[:128] if request_id else None,
                    )
                )
                await db.commit()
        except Exception:
            logger.exception(
                "administrative audit persistence failed",
                extra={"method": request.method, "path": request.url.path},
            )

        return response
