from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_user
from app.core.utils import utc_now
from app.models.class_model import Class
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.payment import Payment, PaymentStatus
from app.models.student import Student
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.payment import (
    PaymentAdminCreate,
    PaymentCreate,
    PaymentResponse,
    PaymentUpdate,
    PaymentWebhookRequest,
)
from app.services.mercado_pago_service import MercadoPagoError, MercadoPagoService

router = APIRouter()


def _amounts_match(a: float, b: float) -> bool:
    """Compara valores monetários com tolerância de centavos."""
    return abs(float(a) - float(b)) < 0.005


@router.post("/", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payment_data: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Cria um pagamento para uma matrícula existente.

    O valor é sempre calculado server-side a partir de ``Enrollment.price``.
    O cliente nunca é autoridade do preço.
    """
    is_admin = current_user.get("role") in ("admin", "super_admin")
    stmt = select(Enrollment).where(Enrollment.id == payment_data.enrollment_id)
    if not is_admin:
        stmt = stmt.join(Student).where(Student.user_id == UUID(current_user["user_id"]))

    result = await db.execute(stmt)
    enrollment = result.scalar_one_or_none()

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found",
        )

    payment = Payment(
        enrollment_id=enrollment.id,
        amount=enrollment.price,
        method=payment_data.method,
        installments=payment_data.installments,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return payment


@router.post(
    "/admin",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment_admin(
    payment_data: PaymentAdminCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Criação administrativa explícita de pagamento com valor manual.

    Reservada para fluxos auditáveis (ex.: pagamento consolidado em lote).
    Requer papel admin/super_admin.
    """
    enrollment = await db.get(Enrollment, payment_data.enrollment_id)
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found",
        )

    payment = Payment(
        enrollment_id=enrollment.id,
        amount=payment_data.amount,
        method=payment_data.method,
        installments=payment_data.installments,
    )
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
    if not request.id or not request.external_reference:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment id and external reference are required",
        )

    try:
        enrollment_id = UUID(request.external_reference)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid external reference",
        )

    stmt = (
        select(Payment, Tenant)
        .join(Tenant, Payment.tenant_id == Tenant.id)
        .where(Payment.enrollment_id == enrollment_id)
        .order_by(Payment.created_at.desc())
    )
    result = await db.execute(stmt.limit(1))
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    _payment, tenant = row
    access_token = (tenant.settings or {}).get("mp_access_token")

    try:
        mp_payment = await MercadoPagoService.get_payment_info(
            request.id, access_token
        )
    except MercadoPagoError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Mercado Pago verification failed: {exc}",
        ) from exc

    mp_external_reference = str(mp_payment.get("external_reference") or "")
    if mp_external_reference != request.external_reference:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="External reference mismatch",
        )

    preference_id = mp_payment.get("preference_id")
    if not preference_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Mercado Pago preference",
        )

    stmt = (
        select(Payment, Enrollment)
        .join(Enrollment, Payment.enrollment_id == Enrollment.id)
        .where(Payment.mercado_pago_id == preference_id)
    )
    result = await db.execute(stmt)
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment preference not found",
        )

    payment, enrollment = row
    if payment.enrollment_id != enrollment_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enrollment mismatch",
        )

    status_map = {
        "approved": PaymentStatus.APROVADO,
        "pending": PaymentStatus.PROCESSANDO,
        "in_process": PaymentStatus.PROCESSANDO,
        "in_mediation": PaymentStatus.PROCESSANDO,
        "rejected": PaymentStatus.RECUSADO,
        "cancelled": PaymentStatus.RECUSADO,
        "refunded": PaymentStatus.REEMBOLSADO,
        "charged_back": PaymentStatus.REEMBOLSADO,
    }
    mp_status = mp_payment.get("status", "unknown")
    new_status = status_map.get(mp_status, PaymentStatus.PENDENTE)

    if payment.status == new_status:
        return {"status": "ok"}

    payment.status = new_status
    if new_status == PaymentStatus.APROVADO:
        payment.paid_at = utc_now()
        # Segurança: só libera o curso quando o valor pago é consistente com
        # o preço autoritativo da matrícula. Um pagamento inconsistente nunca
        # deve confirmar uma matrícula de curso.
        if not _amounts_match(payment.amount, enrollment.price):
            await db.commit()
            return {"status": "amount_mismatch", "detail": "Payment amount does not match enrollment price"}
        if enrollment.status != EnrollmentStatus.CONFIRMADA:
            enrollment.status = EnrollmentStatus.CONFIRMADA

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


@router.post("/{payment_id}/checkout")
async def create_mercado_pago_checkout(
    payment_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    stmt = (
        select(Payment, Enrollment, Student, User, Class, Course)
        .join(Enrollment, Payment.enrollment_id == Enrollment.id)
        .join(Student, Enrollment.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .join(Class, Enrollment.class_id == Class.id)
        .join(Course, Class.course_id == Course.id)
        .where(Payment.id == payment_id)
    )
    result = await db.execute(stmt)
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    payment, enrollment, _student, user, _class, course = row

    is_owner = str(user.id) == current_user["user_id"]
    is_admin = current_user.get("role") in ("admin", "super_admin")
    if not (is_owner or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot checkout a payment that does not belong to you",
        )

    tenant_id = getattr(request.state, "tenant_id", None)
    access_token = None
    if tenant_id:
        tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = tenant_result.scalar_one_or_none()
        if tenant and tenant.settings:
            access_token = tenant.settings.get("mp_access_token")

    try:
        preference = await MercadoPagoService.create_preference(
            enrollment_id=str(enrollment.id),
            amount=payment.amount,
            student_email=user.email,
            course_name=course.name,
            access_token=access_token,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    payment.mercado_pago_id = preference.get("id")
    payment.status = PaymentStatus.PROCESSANDO
    await db.commit()

    return {"checkout_url": preference.get("init_point"), "preference_id": preference.get("id")}
