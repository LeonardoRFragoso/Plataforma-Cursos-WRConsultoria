from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id
from app.services.periodic_payment_reconciliation import reconcile_tenant_payments

router = APIRouter()


@router.post("/run")
async def run_periodic_reconciliation(
    limit: int = 250,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Poll provider payment state without creating charges or refunds."""
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 1000")
    tenant_id = get_current_tenant_id()
    try:
        result = await reconcile_tenant_payments(db, tenant_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"tenant_id": str(tenant_id), **result}
