"""Best-effort transactional notifications for business journeys.

These helpers intentionally run *after* the business transaction is committed.
Email delivery failure must never roll back registration, payment, enrollment,
or course access.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.class_model import Class
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.student import Student
from app.models.tenant import Tenant
from app.models.user import User
from app.services.email_service import EmailServiceError, get_email_service

logger = logging.getLogger(__name__)


def _tenant_frontend_url(tenant: Tenant | None) -> str:
    """Resolve a trusted frontend base URL for tenant-aware email links."""
    if tenant:
        domain_status = getattr(tenant.custom_domain_status, "value", tenant.custom_domain_status)
        if tenant.custom_domain and domain_status in {"VERIFIED", "ACTIVE"}:
            return f"https://{tenant.custom_domain.strip('/')}"

        configured_url = (tenant.settings or {}).get("frontend_url")
        if configured_url:
            return str(configured_url).rstrip("/")

    return settings.FRONTEND_URL.rstrip("/")


async def send_welcome_notification(
    db: AsyncSession,
    user: User,
    tenant_id: UUID,
) -> bool:
    """Send the public-registration welcome email without affecting registration."""
    try:
        tenant = await db.get(Tenant, tenant_id)
        tenant_name = tenant.name if tenant else "Plataforma"
        frontend_url = _tenant_frontend_url(tenant)
        return await get_email_service().send_welcome(
            to=user.email,
            full_name=user.full_name,
            frontend_url=frontend_url,
            tenant_name=tenant_name,
        )
    except EmailServiceError:
        logger.warning("Welcome email delivery failed for user %s", user.id)
    except Exception:
        logger.exception("Unexpected welcome notification failure for user %s", user.id)
    return False


async def send_course_access_notification(
    db: AsyncSession,
    enrollment: Enrollment,
) -> bool:
    """Notify a student after the enrollment is newly confirmed by payment."""
    try:
        stmt = (
            select(User, Course, Tenant)
            .select_from(Enrollment)
            .join(Student, Enrollment.student_id == Student.id)
            .join(User, Student.user_id == User.id)
            .join(Class, Enrollment.class_id == Class.id)
            .join(Course, Class.course_id == Course.id)
            .join(Tenant, Enrollment.tenant_id == Tenant.id)
            .where(
                Enrollment.id == enrollment.id,
                Enrollment.tenant_id == enrollment.tenant_id,
                Student.tenant_id == enrollment.tenant_id,
                User.tenant_id == enrollment.tenant_id,
                Class.tenant_id == enrollment.tenant_id,
                Course.tenant_id == enrollment.tenant_id,
            )
        )
        row = (await db.execute(stmt)).first()
        if not row:
            logger.warning(
                "Course-access notification context not found for enrollment %s",
                enrollment.id,
            )
            return False

        user, course, tenant = row
        frontend_url = _tenant_frontend_url(tenant)
        course_url = f"{frontend_url}/courses/{course.id}/learn"
        return await get_email_service().send_course_access(
            to=user.email,
            full_name=user.full_name,
            course_name=course.name,
            course_url=course_url,
            tenant_name=tenant.name,
        )
    except EmailServiceError:
        logger.warning(
            "Course-access email delivery failed for enrollment %s",
            enrollment.id,
        )
    except Exception:
        logger.exception(
            "Unexpected course-access notification failure for enrollment %s",
            enrollment.id,
        )
    return False
