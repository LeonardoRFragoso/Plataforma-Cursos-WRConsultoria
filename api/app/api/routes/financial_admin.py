from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id
from app.core.utils import utc_now
from app.models.certificate import Certificate
from app.models.company import Company
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.financial_review import FinancialReview, FinancialReviewEvent
from app.models.payment import Payment, PaymentStatus
from app.schemas.financial import (
    CorporatePaymentCreate,
    CorporatePaymentResponse,
    FinancialReviewClaim,
    FinancialReviewEventResponse,
    FinancialReviewResolution,
    FinancialReviewResponse,
    FinancialSummaryResponse,
    ManualReviewCreate,
)
from app.services.financial_review_service import (
    ensure_payment_review,
    materialize_pending_reviews,
)

router = APIRouter()
_REVIEW_STATUSES = {"OPEN", "IN_REVIEW", "RESOLVED", "DISMISSED"}
_RESOLUTION_ACTIONS = {
    "KEEP_ACCESS",
    "REVOKE_ACCESS",
    "MARK_APPROVED",
    "MARK_REFUNDED",
    "DISMISS",
}


def _review_response(review: FinancialReview, payment: Payment) -> FinancialReviewResponse:
    return FinancialReviewResponse(
        id=review.id,
        payment_id=payment.id,
        status=review.status,
        reason=review.reason,
        priority=review.priority,
        assigned_to=review.assigned_to,
        resolution_action=review.resolution_action,
        resolution_notes=review.resolution_notes,
        resolved_by=review.resolved_by,
        resolved_at=review.resolved_at,
        payment_status=payment.status,
        payment_amount=payment.amount,
        provider=payment.provider,
        provider_payment_id=payment.provider_payment_id,
        enrollment_id=payment.enrollment_id,
        company_id=payment.company_id,
        review_required=payment.review_required,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


async def _load_review(db: AsyncSession, tenant_id: UUID, review_id: UUID):
    row = (
        await db.execute(
            select(FinancialReview, Payment)
            .join(Payment, FinancialReview.payment_id == Payment.id)
            .where(
                FinancialReview.id == review_id,
                FinancialReview.tenant_id == tenant_id,
                Payment.tenant_id == tenant_id,
            )
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Financial review not found")
    return row


@router.get("/reviews", response_model=list[FinancialReviewResponse])
async def list_financial_reviews(
    status_filter: str | None = None,
    priority: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await materialize_pending_reviews(db, tenant_id)
    await db.commit()

    stmt = (
        select(FinancialReview, Payment)
        .join(Payment, FinancialReview.payment_id == Payment.id)
        .where(
            FinancialReview.tenant_id == tenant_id,
            Payment.tenant_id == tenant_id,
        )
    )
    if status_filter:
        normalized = status_filter.upper()
        if normalized not in _REVIEW_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid review status")
        stmt = stmt.where(FinancialReview.status == normalized)
    if priority:
        stmt = stmt.where(FinancialReview.priority == priority.upper())
    rows = (await db.execute(stmt.order_by(FinancialReview.created_at.desc()))).all()
    return [_review_response(review, payment) for review, payment in rows]


@router.get("/reviews/{review_id}/events", response_model=list[FinancialReviewEventResponse])
async def review_events(
    review_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _load_review(db, tenant_id, review_id)
    events = (
        await db.execute(
            select(FinancialReviewEvent)
            .where(
                FinancialReviewEvent.tenant_id == tenant_id,
                FinancialReviewEvent.review_id == review_id,
            )
            .order_by(FinancialReviewEvent.created_at.desc())
        )
    ).scalars().all()
    return events


@router.post("/reviews/{review_id}/claim", response_model=FinancialReviewResponse)
async def claim_review(
    review_id: UUID,
    payload: FinancialReviewClaim,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    review, payment = await _load_review(db, tenant_id, review_id)
    if review.status not in ("OPEN", "IN_REVIEW"):
        raise HTTPException(status_code=409, detail="Financial review is already closed")
    actor = UUID(current_user["user_id"])
    if review.assigned_to and review.assigned_to != actor:
        raise HTTPException(status_code=409, detail="Financial review is assigned to another administrator")
    review.status = "IN_REVIEW"
    review.assigned_to = actor
    if payload.priority:
        review.priority = payload.priority.upper()
    db.add(
        FinancialReviewEvent(
            tenant_id=tenant_id,
            review_id=review.id,
            payment_id=payment.id,
            event_type="CLAIMED",
            actor_id=actor,
            details=f"priority={review.priority}",
        )
    )
    await db.commit()
    await db.refresh(review)
    return _review_response(review, payment)


@router.post("/payments/{payment_id}/review", response_model=FinancialReviewResponse)
async def open_manual_review(
    payment_id: UUID,
    payload: ManualReviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    payment = (
        await db.execute(select(Payment).where(Payment.id == payment_id, Payment.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    payment.review_required = True
    payment.review_reason = payload.reason.strip()
    review = await ensure_payment_review(db, payment, source="manual_admin")
    if not review:
        raise HTTPException(status_code=500, detail="Could not create financial review")
    review.priority = payload.priority.upper()
    await db.commit()
    await db.refresh(review)
    return _review_response(review, payment)


async def _certificate_exists(db: AsyncSession, tenant_id: UUID, enrollment_id: UUID) -> bool:
    return (
        await db.scalar(
            select(func.count(Certificate.id)).where(
                Certificate.tenant_id == tenant_id,
                Certificate.enrollment_id == enrollment_id,
            )
        )
        or 0
    ) > 0


@router.post("/reviews/{review_id}/resolve", response_model=FinancialReviewResponse)
async def resolve_review(
    review_id: UUID,
    payload: FinancialReviewResolution,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    review, payment = await _load_review(db, tenant_id, review_id)
    if review.status not in ("OPEN", "IN_REVIEW"):
        raise HTTPException(status_code=409, detail="Financial review is already closed")
    action = payload.action.upper()
    if action not in _RESOLUTION_ACTIONS:
        raise HTTPException(status_code=400, detail="Invalid financial resolution action")

    enrollment = None
    if payment.enrollment_id:
        enrollment = (
            await db.execute(
                select(Enrollment).where(
                    Enrollment.id == payment.enrollment_id,
                    Enrollment.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()

    if action == "REVOKE_ACCESS":
        if not enrollment:
            raise HTTPException(status_code=409, detail="Payment has no individual enrollment")
        if enrollment.status == EnrollmentStatus.CONCLUIDA or await _certificate_exists(db, tenant_id, enrollment.id):
            raise HTTPException(
                status_code=409,
                detail="Completed/certified learning history cannot be revoked automatically",
            )
        enrollment.status = EnrollmentStatus.CANCELADA
    elif action == "MARK_APPROVED":
        payment.status = PaymentStatus.APROVADO
        payment.paid_at = payment.paid_at or utc_now()
        if enrollment and enrollment.status == EnrollmentStatus.PENDENTE:
            enrollment.status = EnrollmentStatus.CONFIRMADA
    elif action == "MARK_REFUNDED":
        payment.status = PaymentStatus.REEMBOLSADO
        if enrollment:
            protected = (
                enrollment.status == EnrollmentStatus.CONCLUIDA
                or await _certificate_exists(db, tenant_id, enrollment.id)
            )
            if not protected and enrollment.status in (EnrollmentStatus.PENDENTE, EnrollmentStatus.CONFIRMADA):
                enrollment.status = EnrollmentStatus.CANCELADA

    payment.review_required = False
    payment.review_reason = None
    actor = UUID(current_user["user_id"])
    review.status = "DISMISSED" if action == "DISMISS" else "RESOLVED"
    review.resolution_action = action
    review.resolution_notes = payload.notes.strip()
    review.resolved_by = actor
    review.resolved_at = utc_now()
    review.assigned_to = review.assigned_to or actor
    db.add(
        FinancialReviewEvent(
            tenant_id=tenant_id,
            review_id=review.id,
            payment_id=payment.id,
            event_type=review.status,
            actor_id=actor,
            details=f"action={action};notes={review.resolution_notes}",
        )
    )
    await db.commit()
    await db.refresh(review)
    await db.refresh(payment)
    return _review_response(review, payment)


@router.post("/corporate-payments", response_model=CorporatePaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_corporate_payment(
    payload: CorporatePaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Create an auditable consolidated B2B receivable without an enrollment."""
    tenant_id = get_current_tenant_id()
    company = (
        await db.execute(
            select(Company).where(Company.id == payload.company_id, Company.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if company.status.upper() != "ACTIVE":
        raise HTTPException(status_code=409, detail="Company is not active")

    payment = Payment(
        tenant_id=tenant_id,
        company_id=company.id,
        enrollment_id=None,
        amount=payload.amount,
        method=payload.method,
        provider=payload.provider,
        installments=payload.installments,
    )
    if payload.reference:
        payment.review_reason = f"corporate_reference:{payload.reference.strip()}"
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return payment


@router.get("/corporate-payments/{company_id}", response_model=list[CorporatePaymentResponse])
async def list_corporate_payments(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    payments = (
        await db.execute(
            select(Payment)
            .where(
                Payment.tenant_id == tenant_id,
                Payment.company_id == company_id,
                Payment.enrollment_id.is_(None),
            )
            .order_by(Payment.created_at.desc())
        )
    ).scalars().all()
    return payments


@router.get("/summary", response_model=FinancialSummaryResponse)
async def financial_summary(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await materialize_pending_reviews(db, tenant_id)
    start_of_month = utc_now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    async def amount(status_value, *, since=None):
        stmt = select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.tenant_id == tenant_id,
            Payment.status == status_value,
        )
        if since:
            stmt = stmt.where(Payment.created_at >= since)
        return float(await db.scalar(stmt) or 0)

    async def count_payment(status_value):
        return int(
            await db.scalar(
                select(func.count(Payment.id)).where(
                    Payment.tenant_id == tenant_id,
                    Payment.status == status_value,
                )
            )
            or 0
        )

    approved_total = await amount(PaymentStatus.APROVADO)
    refunded_total = await amount(PaymentStatus.REEMBOLSADO)
    monthly_approved = await amount(PaymentStatus.APROVADO, since=start_of_month)
    monthly_refunded = await amount(PaymentStatus.REEMBOLSADO, since=start_of_month)
    open_reviews = int(
        await db.scalar(
            select(func.count(FinancialReview.id)).where(
                FinancialReview.tenant_id == tenant_id,
                FinancialReview.status == "OPEN",
            )
        )
        or 0
    )
    in_review = int(
        await db.scalar(
            select(func.count(FinancialReview.id)).where(
                FinancialReview.tenant_id == tenant_id,
                FinancialReview.status == "IN_REVIEW",
            )
        )
        or 0
    )
    corporate_payments = int(
        await db.scalar(
            select(func.count(Payment.id)).where(
                Payment.tenant_id == tenant_id,
                Payment.company_id.is_not(None),
                Payment.enrollment_id.is_(None),
            )
        )
        or 0
    )
    await db.commit()
    return FinancialSummaryResponse(
        approved_total=approved_total,
        refunded_total=refunded_total,
        net_total=approved_total - refunded_total,
        monthly_approved=monthly_approved,
        monthly_refunded=monthly_refunded,
        monthly_net=monthly_approved - monthly_refunded,
        open_reviews=open_reviews,
        in_review=in_review,
        pending_payments=await count_payment(PaymentStatus.PENDENTE),
        processing_payments=await count_payment(PaymentStatus.PROCESSANDO),
        approved_payments=await count_payment(PaymentStatus.APROVADO),
        refunded_payments=await count_payment(PaymentStatus.REEMBOLSADO),
        expired_payments=await count_payment(PaymentStatus.EXPIRADO),
        corporate_payments=corporate_payments,
    )
