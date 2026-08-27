from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id
from app.models.governance import AdminAuditLog
from app.schemas.governance import AdminAuditLogResponse

router = APIRouter()


@router.get("/audit", response_model=list[AdminAuditLogResponse])
async def list_admin_audit_logs(
    actor_id: UUID | None = None,
    method: str | None = None,
    status_code: int | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """List tenant-scoped mutation metadata; request bodies are never stored."""
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")

    tenant_id = get_current_tenant_id()
    stmt = select(AdminAuditLog).where(AdminAuditLog.tenant_id == tenant_id)
    if actor_id:
        stmt = stmt.where(AdminAuditLog.actor_id == actor_id)
    if method:
        normalized_method = method.strip().upper()
        if normalized_method not in {"POST", "PUT", "PATCH", "DELETE"}:
            raise HTTPException(status_code=400, detail="Invalid audit method")
        stmt = stmt.where(AdminAuditLog.method == normalized_method)
    if status_code is not None:
        if status_code < 100 or status_code > 599:
            raise HTTPException(status_code=400, detail="Invalid HTTP status code")
        stmt = stmt.where(AdminAuditLog.status_code == status_code)

    return (
        await db.execute(
            stmt.order_by(AdminAuditLog.created_at.desc()).limit(limit)
        )
    ).scalars().all()
