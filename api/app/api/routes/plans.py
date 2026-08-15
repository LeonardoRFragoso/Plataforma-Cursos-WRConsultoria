"""Planos comerciais da WR (catálogo SaaS White Label).

O catálogo de Plan é controlado pela WR (SUPER_ADMIN). Tenants comuns
apenas consultam os planos públicos disponíveis. O CRUD administrativo
fica em ``app.api.routes.super_admin``.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.plan import Plan
from app.schemas.plan import PlanResponse

router = APIRouter()


@router.get("/public", response_model=list[PlanResponse])
async def list_public_plans(
    db: AsyncSession = Depends(get_db),
):
    """Lista os planos comerciais públicos ativos da WR.

    Endpoint público (sem autenticação). Retorna apenas planos do catálogo
    global (tenant_id IS NULL) e ativos.
    """
    stmt = select(Plan).where(
        Plan.tenant_id.is_(None),
        Plan.is_active.is_(True),
    )
    result = await db.execute(stmt)
    return result.scalars().all()
