from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id
from app.core.utils import utc_now
from app.models.certificate import Certificate
from app.models.class_model import Class, ClassStatus
from app.models.company import Company
from app.models.corporate import CorporateInvite, CorporateSeatAllocation, CorporateTrainingRequest
from app.models.enrollment import Enrollment, EnrollmentSource, EnrollmentStatus
from app.models.financial_review import FinancialReview
from app.models.payment import Payment, PaymentStatus
from app.models.student import Student

router = APIRouter()


async def _count(db: AsyncSession, model, *where) -> int:
    return int(await db.scalar(select(func.count(model.id)).where(*where)) or 0)


async def _sum(db: AsyncSession, column, *where) -> float:
    return float(await db.scalar(select(func.coalesce(func.sum(column), 0)).where(*where)) or 0)


@router.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Backward-compatible dashboard stats plus operational KPIs."""
    tenant_id = get_current_tenant_id()
    now = utc_now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    in_30_days = now + timedelta(days=30)

    total_students = await _count(db, Student, Student.tenant_id == tenant_id)
    active_classes = await _count(
        db,
        Class,
        Class.tenant_id == tenant_id,
        Class.status.in_([ClassStatus.ABERTA, ClassStatus.EM_ANDAMENTO]),
    )
    pending_enrollments = await _count(
        db,
        Enrollment,
        Enrollment.tenant_id == tenant_id,
        Enrollment.status == EnrollmentStatus.PENDENTE,
    )
    monthly_revenue = await _sum(
        db,
        Payment.amount,
        Payment.tenant_id == tenant_id,
        Payment.status == PaymentStatus.APROVADO,
        Payment.created_at >= start_of_month,
    )
    monthly_refunds = await _sum(
        db,
        Payment.amount,
        Payment.tenant_id == tenant_id,
        Payment.status == PaymentStatus.REEMBOLSADO,
        Payment.created_at >= start_of_month,
    )
    completed_enrollments = await _count(
        db,
        Enrollment,
        Enrollment.tenant_id == tenant_id,
        Enrollment.status == EnrollmentStatus.CONCLUIDA,
    )
    total_enrollments = await _count(db, Enrollment, Enrollment.tenant_id == tenant_id)

    return {
        "totalStudents": total_students,
        "activeClasses": active_classes,
        "pendingEnrollments": pending_enrollments,
        "monthlyRevenue": monthly_revenue,
        "monthlyRefunds": monthly_refunds,
        "monthlyNetRevenue": monthly_revenue - monthly_refunds,
        "totalCompanies": await _count(db, Company, Company.tenant_id == tenant_id),
        "corporateEnrollments": await _count(
            db,
            Enrollment,
            Enrollment.tenant_id == tenant_id,
            Enrollment.source == EnrollmentSource.CORPORATE,
        ),
        "completionRate": round((completed_enrollments / total_enrollments) * 100, 2)
        if total_enrollments
        else 0.0,
        "activeCertificates": await _count(
            db,
            Certificate,
            Certificate.tenant_id == tenant_id,
            Certificate.status == "ACTIVE",
            or_(Certificate.expires_at.is_(None), Certificate.expires_at > now),
        ),
        "expiringCertificates30d": await _count(
            db,
            Certificate,
            Certificate.tenant_id == tenant_id,
            Certificate.status == "ACTIVE",
            Certificate.expires_at.is_not(None),
            Certificate.expires_at > now,
            Certificate.expires_at <= in_30_days,
        ),
        "revokedCertificates": await _count(
            db,
            Certificate,
            Certificate.tenant_id == tenant_id,
            Certificate.status == "REVOKED",
        ),
        "openFinancialReviews": await _count(
            db,
            FinancialReview,
            FinancialReview.tenant_id == tenant_id,
            FinancialReview.status.in_(["OPEN", "IN_REVIEW"]),
        ),
        "newCorporateRequests": await _count(
            db,
            CorporateTrainingRequest,
            CorporateTrainingRequest.tenant_id == tenant_id,
            CorporateTrainingRequest.status == "NEW",
        ),
    }


@router.get("/operations")
async def operations_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Operator cockpit: queues and KPIs that require administrator attention."""
    tenant_id = get_current_tenant_id()
    now = utc_now()
    in_30_days = now + timedelta(days=30)

    payment_counts = {}
    for status_value in PaymentStatus:
        payment_counts[status_value.value] = await _count(
            db,
            Payment,
            Payment.tenant_id == tenant_id,
            Payment.status == status_value,
        )

    open_reviews = (
        await db.execute(
            select(FinancialReview, Payment)
            .join(Payment, FinancialReview.payment_id == Payment.id)
            .where(
                FinancialReview.tenant_id == tenant_id,
                FinancialReview.status.in_(["OPEN", "IN_REVIEW"]),
                Payment.tenant_id == tenant_id,
            )
            .order_by(FinancialReview.created_at.asc())
            .limit(8)
        )
    ).all()
    corporate_requests = (
        await db.execute(
            select(CorporateTrainingRequest)
            .where(
                CorporateTrainingRequest.tenant_id == tenant_id,
                CorporateTrainingRequest.status.not_in(["WON", "LOST"]),
            )
            .order_by(CorporateTrainingRequest.created_at.asc())
            .limit(8)
        )
    ).scalars().all()
    expiring_certificates = (
        await db.execute(
            select(Certificate)
            .where(
                Certificate.tenant_id == tenant_id,
                Certificate.status == "ACTIVE",
                Certificate.expires_at.is_not(None),
                Certificate.expires_at > now,
                Certificate.expires_at <= in_30_days,
            )
            .order_by(Certificate.expires_at.asc())
            .limit(8)
        )
    ).scalars().all()

    total_reserved = await _sum(
        db,
        CorporateSeatAllocation.seats_reserved,
        CorporateSeatAllocation.tenant_id == tenant_id,
        CorporateSeatAllocation.is_active.is_(True),
    )
    corporate_used = await _count(
        db,
        Enrollment,
        Enrollment.tenant_id == tenant_id,
        Enrollment.source == EnrollmentSource.CORPORATE,
        Enrollment.status != EnrollmentStatus.CANCELADA,
    )

    return {
        "summary": await get_dashboard_stats(db=db, current_user=current_user),
        "payments": payment_counts,
        "corporate": {
            "companies": await _count(db, Company, Company.tenant_id == tenant_id),
            "pendingInvites": await _count(
                db,
                CorporateInvite,
                CorporateInvite.tenant_id == tenant_id,
                CorporateInvite.status == "PENDING",
            ),
            "seatReserved": int(total_reserved),
            "seatUsed": corporate_used,
            "seatUtilization": round((corporate_used / total_reserved) * 100, 2)
            if total_reserved
            else 0.0,
        },
        "queues": {
            "financialReviews": [
                {
                    "id": review.id,
                    "payment_id": payment.id,
                    "reason": review.reason,
                    "priority": review.priority,
                    "status": review.status,
                    "amount": payment.amount,
                    "provider": payment.provider.value,
                    "created_at": review.created_at,
                }
                for review, payment in open_reviews
            ],
            "corporateRequests": [
                {
                    "id": item.id,
                    "company_name": item.company_name,
                    "contact_name": item.contact_name,
                    "contact_email": item.contact_email,
                    "employee_count": item.employee_count,
                    "course_interest": item.course_interest,
                    "status": item.status,
                    "created_at": item.created_at,
                }
                for item in corporate_requests
            ],
            "expiringCertificates": [
                {
                    "id": item.id,
                    "certificate_number": item.certificate_number,
                    "expires_at": item.expires_at,
                    "version": item.version,
                }
                for item in expiring_certificates
            ],
        },
    }
