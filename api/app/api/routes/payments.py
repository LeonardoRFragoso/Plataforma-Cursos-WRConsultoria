from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.context import current_tenant_id
from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id, get_current_user
from app.models.class_model import Class
from app.models.company import Company
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.payment import Payment, PaymentProvider, PaymentStatus
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
from app.services.payment_customer_sync import (
    get_or_create_company_customer,
    get_or_create_student_customer,
)
from app.services.payment_provider_base import (
    PaymentProviderError,
    resolve_provider,
)
from app.services.payment_reconciliation import reconcile_payment_status
from app.services.tenant_secret_service import get_mercado_pago_access_token

router = APIRouter()


def _demo_payment_guard():
    """Garante que endpoints de demo só existam fora de produção com mock mode."""
    if settings.ENVIRONMENT.lower() == "production":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )
    if not settings.MERCADO_PAGO_MOCK_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo payment endpoints require MERCADO_PAGO_MOCK_MODE=true",
        )


async def _load_payment_with_context(db: AsyncSession, payment_id: UUID, tenant_id: UUID):
    """Load payment with enrollment, student, user, class, course.

    Returns (payment, enrollment, student, user, class_obj, course) or None.
    """
    stmt = (
        select(Payment, Enrollment, Student, User, Class, Course)
        .join(Enrollment, Payment.enrollment_id == Enrollment.id)
        .join(Student, Enrollment.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .join(Class, Enrollment.class_id == Class.id)
        .join(Course, Class.course_id == Course.id)
        .where(
            Payment.id == payment_id,
            Payment.tenant_id == tenant_id,
        )
    )
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        return None
    return row


async def _payment_response_with_course_context(
    db: AsyncSession,
    payment: Payment,
    tenant_id: UUID,
) -> PaymentResponse:
    """Enrich an individual payment with course/enrollment return context."""
    response = PaymentResponse.model_validate(payment)
    if not payment.enrollment_id:
        return response

    stmt = (
        select(Course.id, Enrollment.status)
        .select_from(Enrollment)
        .join(Class, Enrollment.class_id == Class.id)
        .join(Course, Class.course_id == Course.id)
        .where(
            Enrollment.id == payment.enrollment_id,
            Enrollment.tenant_id == tenant_id,
            Course.tenant_id == tenant_id,
        )
    )
    row = (await db.execute(stmt)).first()
    if not row:
        return response

    course_id, enrollment_status = row
    return response.model_copy(
        update={
            "course_id": course_id,
            "enrollment_status": enrollment_status,
        }
    )


def _authorize_payment_access(row, current_user: dict) -> None:
    """Shared authorization for demo payment GET and POST endpoints.

    A student may only access their OWN payment.
    An admin/super_admin of the resolved tenant may access tenant payments.
    A different student in the same tenant gets 403.
    A user from another tenant gets 403.

    Raises HTTPException(403) if unauthorized.
    """
    _payment, _enrollment, _student, user, _class, _course = row
    is_owner = str(user.id) == current_user["user_id"]
    is_admin = current_user.get("role") in ("admin", "super_admin")
    if not (is_owner or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this payment",
        )


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
    tenant_id = get_current_tenant_id()
    stmt = select(Enrollment).where(
        Enrollment.id == payment_data.enrollment_id,
        Enrollment.tenant_id == tenant_id,
    )
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
        tenant_id=tenant_id,
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
    tenant_id = get_current_tenant_id()
    enrollment = await db.get(Enrollment, payment_data.enrollment_id)
    if not enrollment or enrollment.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found",
        )

    payment = Payment(
        tenant_id=tenant_id,
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
    tenant_id = get_current_tenant_id()
    stmt = select(Payment).where(Payment.tenant_id == tenant_id).offset(skip).limit(limit)
    result = await db.execute(stmt)
    payments = result.scalars().all()
    return payments


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    stmt = select(Payment).where(
        Payment.id == payment_id,
        Payment.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    is_admin = current_user.get("role") in ("admin", "super_admin")
    if is_admin:
        return await _payment_response_with_course_context(db, payment, tenant_id)

    # Student: only own payments (via enrollment->student->user)
    if payment.enrollment_id:
        ownership_stmt = (
            select(Payment)
            .join(Enrollment, Payment.enrollment_id == Enrollment.id)
            .join(Student, Enrollment.student_id == Student.id)
            .join(User, Student.user_id == User.id)
            .where(
                Payment.id == payment_id,
                Payment.tenant_id == tenant_id,
                User.id == UUID(current_user["user_id"]),
            )
        )
        if (await db.execute(ownership_stmt)).scalar_one_or_none():
            return await _payment_response_with_course_context(db, payment, tenant_id)

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to access this payment",
    )


@router.put("/{payment_id}", response_model=PaymentResponse)
async def update_payment(
    payment_id: UUID,
    payment_data: PaymentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(Payment).where(
        Payment.id == payment_id,
        Payment.tenant_id == tenant_id,
    )
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
        external_ref_uuid = UUID(request.external_reference)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid external reference",
        )

    # Look up Payment by external_reference.
    # New format: external_reference = str(payment_id) → look up by Payment.id
    # Old format: external_reference = str(enrollment_id) → look up by enrollment_id
    stmt = (
        select(Payment, Tenant)
        .join(Tenant, Payment.tenant_id == Tenant.id)
        .where(Payment.id == external_ref_uuid)
        .order_by(Payment.created_at.desc())
    )
    result = await db.execute(stmt.limit(1))
    row = result.first()

    if not row:
        # Fallback: try looking up by enrollment_id (backward compat)
        stmt = (
            select(Payment, Tenant)
            .join(Tenant, Payment.tenant_id == Tenant.id)
            .where(Payment.enrollment_id == external_ref_uuid)
            .order_by(Payment.created_at.desc())
        )
        result = await db.execute(stmt.limit(1))
        row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    payment, tenant = row
    # Access token do Mercado Pago lido do TenantSecret criptografado.
    # Fallback legado: tenant.settings["mp_access_token"] (descontinuado,
    # mantido apenas para janela de migração pós-deploy).
    access_token = await get_mercado_pago_access_token(db, tenant.id)
    if not access_token:
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
    # Verify the payment matches the one we found earlier
    if payment.id != external_ref_uuid and payment.enrollment_id != external_ref_uuid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment mismatch",
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

    # Use shared reconciliation service — same logic as demo simulator
    result = await reconcile_payment_status(payment, enrollment, new_status)
    await db.commit()

    if not result["amount_match"]:
        return {"status": "amount_mismatch", "detail": "Payment amount does not match enrollment price"}
    return {"status": "ok"}


@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(Payment).where(
        Payment.id == payment_id,
        Payment.tenant_id == tenant_id,
    )
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
async def create_checkout(
    payment_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create or reuse a provider checkout for an active payment attempt.

    Uses the provider abstraction to support Mercado Pago and Asaas.
    Handles both individual payments (enrollment_id set) and
    consolidated company payments (company_id set, enrollment_id=None).

    Idempotency: pending/processing attempts reuse their existing external
    charge. Terminal attempts are immutable: approved, rejected and refunded
    payments cannot be checked out again. A rejected/refunded purchase must
    obtain a new Payment attempt through the purchase flow, preserving the
    previous row as financial history.
    """
    tenant_id = current_tenant_id.get()
    if tenant_id is None:
        tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant not resolved",
        )

    # Load the payment first (tenant-scoped)
    payment = await db.get(Payment, payment_id)
    if not payment or payment.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    # ── Determine payment type: individual (enrollment) or company ──
    is_company_payment = payment.company_id is not None and payment.enrollment_id is None

    if is_company_payment:
        # Company consolidated payment — load company + class/course
        company = await db.get(Company, payment.company_id)
        if not company or company.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found",
            )

        # Company payments are admin-only (no student owner)
        is_admin = current_user.get("role") in ("admin", "super_admin")
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company payments can only be checked out by admins",
            )

        # Resolve course name from the batch (if available) or use company name
        course_name = f"Treinamento Corporativo - {company.legal_name}"
        customer_email = company.rh_email or f"company-{company.id}@noreply.local"
        customer_name = company.legal_name
    else:
        # Individual payment — load enrollment/student/user/class/course
        stmt = (
            select(Payment, Enrollment, Student, User, Class, Course)
            .join(Enrollment, Payment.enrollment_id == Enrollment.id)
            .join(Student, Enrollment.student_id == Student.id)
            .join(User, Student.user_id == User.id)
            .join(Class, Enrollment.class_id == Class.id)
            .join(Course, Class.course_id == Course.id)
            .where(
                Payment.id == payment_id,
                Payment.tenant_id == tenant_id,
            )
        )
        result = await db.execute(stmt)
        row = result.first()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found",
            )

        _, _enrollment, student, user, _class, course = row
        payment = row[0]  # use the loaded payment from the join

        is_owner = str(user.id) == current_user["user_id"]
        is_admin = current_user.get("role") in ("admin", "super_admin")
        if not (is_owner or is_admin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot checkout a payment that does not belong to you",
            )

        course_name = course.name
        customer_email = user.email
        customer_name = user.full_name

    # ── Terminal attempts are immutable ──
    if payment.status == PaymentStatus.APROVADO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payment already approved",
        )
    if payment.status in (PaymentStatus.RECUSADO, PaymentStatus.REEMBOLSADO):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payment attempt is closed; start a new purchase attempt",
        )
    if float(payment.amount or 0) <= 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Free courses do not require checkout",
        )

    # ── Idempotency: reuse existing external charge if still active ──
    if (
        payment.provider_payment_id
        and payment.checkout_url
        and payment.status in (PaymentStatus.PENDENTE, PaymentStatus.PROCESSANDO)
    ):
        return {
            "checkout_url": payment.checkout_url,
            "preference_id": payment.provider_payment_id,
            "reused": True,
        }

    # ── Resolve tenant settings for provider selection ──
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    tenant_settings = (tenant.settings if tenant else None) or {}

    # ── Resolve the active provider for this tenant ──
    try:
        provider = await resolve_provider(db, tenant_id, tenant_settings)
    except PaymentProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=exc.safe_message,
        ) from exc

    provider_name = provider.provider

    # ── For Asaas: ensure customer exists ──
    customer_id = None
    if provider_name == PaymentProvider.ASAAS:
        try:
            if is_company_payment:
                customer_id = await get_or_create_company_customer(
                    db,
                    provider,
                    tenant_id=tenant_id,
                    company_id=payment.company_id,
                    provider_name=provider_name,
                )
            else:
                customer_id = await get_or_create_student_customer(
                    db,
                    provider,
                    tenant_id=tenant_id,
                    student_id=student.id,
                    provider_name=provider_name,
                )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    # ── Create the checkout/charge at the provider ──
    try:
        checkout = await provider.create_checkout(
            payment_id=payment.id,
            amount=payment.amount,
            student_email=customer_email,
            student_name=customer_name,
            course_name=course_name,
            method=payment.method,
            customer_id=customer_id,
        )
    except PaymentProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=exc.safe_message,
        ) from exc

    # ── Persist provider fields on the payment ──
    payment.provider = provider_name
    payment.provider_payment_id = checkout.provider_payment_id
    payment.checkout_url = checkout.checkout_url
    # Legacy compatibility: also set mercado_pago_id for MP
    if provider_name == PaymentProvider.MERCADO_PAGO:
        payment.mercado_pago_id = checkout.provider_payment_id
    payment.status = PaymentStatus.PROCESSANDO
    await db.commit()

    # ── Mock mode: return relative URL for demo flow ──
    if (
        provider_name == PaymentProvider.MERCADO_PAGO
        and settings.MERCADO_PAGO_MOCK_MODE
        and settings.ENVIRONMENT.lower() != "production"
    ):
        checkout_url = f"/demo/payment/{payment_id}"
        return {"checkout_url": checkout_url, "preference_id": checkout.provider_payment_id}

    if (
        provider_name == PaymentProvider.ASAAS
        and getattr(settings, "ASAAS_MOCK_MODE", False)
        and settings.ENVIRONMENT.lower() != "production"
    ):
        checkout_url = f"/demo/payment/{payment_id}"
        return {"checkout_url": checkout_url, "preference_id": checkout.provider_payment_id}

    return {
        "checkout_url": checkout.checkout_url,
        "preference_id": checkout.provider_payment_id,
    }


# ------------------------------------------------------------------
# Demo payment simulator — only available in non-production with mock mode.
# Uses the SAME shared reconciliation service as the webhook.
# ------------------------------------------------------------------

@router.get("/demo/{payment_id}", response_model=dict)
async def demo_payment_status(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Retorna detalhes do pagamento para a tela de simulação demo."""
    _demo_payment_guard()

    tenant_id = get_current_tenant_id()
    row = await _load_payment_with_context(db, payment_id, tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="Payment not found")

    _authorize_payment_access(row, current_user)

    payment, enrollment, _student, user, _class, course = row
    return {
        "payment_id": str(payment.id),
        "course_id": str(course.id),
        "course_name": course.name,
        "amount": payment.amount,
        "status": payment.status,
        "student_name": user.full_name,
        "enrollment_status": enrollment.status,
    }


@router.post("/demo/{payment_id}/approve", response_model=dict)
async def demo_payment_approve(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Simula pagamento aprovado usando a reconciliação compartilhada."""
    _demo_payment_guard()

    tenant_id = get_current_tenant_id()
    row = await _load_payment_with_context(db, payment_id, tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="Payment not found")

    _authorize_payment_access(row, current_user)

    payment, enrollment, _student, _user, _class, _course = row
    result = await reconcile_payment_status(payment, enrollment, PaymentStatus.APROVADO)
    await db.commit()
    return {"status": "approved", **result}


@router.post("/demo/{payment_id}/reject", response_model=dict)
async def demo_payment_reject(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Simula pagamento rejeitado usando a reconciliação compartilhada."""
    _demo_payment_guard()

    tenant_id = get_current_tenant_id()
    row = await _load_payment_with_context(db, payment_id, tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="Payment not found")

    _authorize_payment_access(row, current_user)

    payment, enrollment, _student, _user, _class, _course = row
    result = await reconcile_payment_status(payment, enrollment, PaymentStatus.RECUSADO)
    await db.commit()
    return {"status": "rejected", **result}


@router.post("/demo/{payment_id}/pending", response_model=dict)
async def demo_payment_pending(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Simula pagamento pendente usando a reconciliação compartilhada."""
    _demo_payment_guard()

    tenant_id = get_current_tenant_id()
    row = await _load_payment_with_context(db, payment_id, tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="Payment not found")

    _authorize_payment_access(row, current_user)

    payment, enrollment, _student, _user, _class, _course = row
    result = await reconcile_payment_status(payment, enrollment, PaymentStatus.PROCESSANDO)
    await db.commit()
    return {"status": "pending", **result}
