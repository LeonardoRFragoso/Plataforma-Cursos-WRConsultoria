from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id
from app.core.utils import utc_now
from app.models.class_model import Class, ClassStatus
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.payment import Payment, PaymentStatus
from app.models.student import Student

router = APIRouter()


@router.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Retorna estatísticas financeiras e operacionais do tenant."""
    tenant_id = get_current_tenant_id()
    # All timestamp columns in this schema are TIMESTAMP WITHOUT TIME ZONE and
    # utc_now() returns a naive UTC datetime. Comparing a tz-aware datetime
    # against a naive column raises asyncpg DataError (offset-naive vs
    # offset-aware), which surfaces in the browser as a CORS-style failure
    # because the unhandled 500 bypasses CORS header injection. Keep this
    # naive to match the column/utc_now() convention.
    start_of_month = utc_now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_students = await db.scalar(
        select(func.count(Student.id)).where(Student.tenant_id == tenant_id)
    )
    # Fix: "ATIVA" was never a valid ClassStatus value.
    # Active classes = ABERTA + EM_ANDAMENTO
    active_classes = await db.scalar(
        select(func.count(Class.id)).where(
            Class.tenant_id == tenant_id,
            Class.status.in_([ClassStatus.ABERTA, ClassStatus.EM_ANDAMENTO]),
        )
    )
    pending_enrollments = await db.scalar(
        select(func.count(Enrollment.id)).where(
            Enrollment.tenant_id == tenant_id,
            Enrollment.status == EnrollmentStatus.PENDENTE,
        )
    )
    monthly_revenue = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.tenant_id == tenant_id,
            Payment.status == PaymentStatus.APROVADO,
            Payment.created_at >= start_of_month,
        )
    )

    return {
        "totalStudents": total_students,
        "activeClasses": active_classes,
        "pendingEnrollments": pending_enrollments,
        "monthlyRevenue": monthly_revenue,
    }
