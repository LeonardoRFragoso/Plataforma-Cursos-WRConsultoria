from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id
from app.models.plan import Plan
from app.schemas.plan import PlanCreate, PlanResponse, PlanUpdate

router = APIRouter()


@router.get("/", response_model=list[PlanResponse])
async def list_plans(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(Plan).where(
        Plan.tenant_id == tenant_id,
        Plan.is_active == True,
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    data: PlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    plan = Plan(tenant_id=tenant_id, **data.model_dump())
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(Plan).where(
        Plan.id == plan_id,
        Plan.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )
    return plan


@router.put("/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: UUID,
    data: PlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(Plan).where(
        Plan.id == plan_id,
        Plan.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)

    await db.commit()
    await db.refresh(plan)
    return plan


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(Plan).where(
        Plan.id == plan_id,
        Plan.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    plan.is_active = False
    await db.commit()
