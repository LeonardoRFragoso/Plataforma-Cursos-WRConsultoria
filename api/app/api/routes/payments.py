from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_user
from app.models.enrollment import Enrollment
from app.models.payment import Payment, PaymentStatus
from app.schemas.payment import (
    PaymentCreate,
    PaymentResponse,
    PaymentUpdate,
    PaymentWebhookRequest,
)

router = APIRouter()

@router.post("/", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payment_data: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    stmt = select(Enrollment).where(Enrollment.id == payment_data.enrollment_id)
    result = await db.execute(stmt)
    enrollment = result.scalar_one_or_none()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found",
        )
    
    payment = Payment(**payment_data.model_dump())
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return payment

@router.get("/", response_model=list[PaymentResponse])
async def list_payments(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
    skip: int = 0,
    limit: int = 100,
):
    stmt = select(Payment).offset(skip).limit(limit)
    result = await db.execute(stmt)
    payments = result.scalars().all()
    return payments

@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    stmt = select(Payment).where(Payment.id == payment_id)
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    
    return payment

@router.put("/{payment_id}", response_model=PaymentResponse)
async def update_payment(
    payment_id: UUID,
    payment_data: PaymentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    stmt = select(Payment).where(Payment.id == payment_id)
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    
    update_data = payment_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(payment, field, value)
    
    await db.commit()
    await db.refresh(payment)
    return payment

@router.post("/webhook/mercado-pago")
async def mercado_pago_webhook(
    request: PaymentWebhookRequest,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Payment).where(Payment.mercado_pago_id == request.id)
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    
    status_map = {
        "approved": PaymentStatus.APROVADO,
        "pending": PaymentStatus.PROCESSANDO,
        "rejected": PaymentStatus.RECUSADO,
        "cancelled": PaymentStatus.RECUSADO,
        "refunded": PaymentStatus.REEMBOLSADO,
    }
    
    payment.status = status_map.get(request.status, PaymentStatus.PENDENTE)
    await db.commit()
    
    return {"status": "ok"}

@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    stmt = select(Payment).where(Payment.id == payment_id)
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    
    await db.delete(payment)
    await db.commit()
