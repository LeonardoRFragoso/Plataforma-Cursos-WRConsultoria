"""Best-effort transactional notifications for business journeys.

These helpers intentionally run *after* the business transaction is committed.
Email delivery failure must never roll back registration, payment, enrollment,
or course access.
"""

from __future__ import annotations

import logging
from urllib.parse import urlsplit
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


def _email_enabled() -> bool:
    """Honor the explicit production email switch when present."""
    return bool(getattr(settings, "EMAIL_ENABLED", True))


def _safe_http_base_url(value: str | None) -> str | None:
    """Accept only absolute HTTP(S) frontend URLs for email links."""
    if not value:
        return None
    candidate = str(value).strip().rstrip("/")
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.username or parsed.password:
        return None
    return candidate


def _tenant_frontend_url(tenant: Tenant | None) -> str:
    """Resolve a trusted frontend base URL for tenant-aware email links."""
    if tenant:
        domain_status = getattr(
            tenant.custom_domain_status,
            "value",
            tenant.custom_domain_status,
        )
        if tenant.custom_domain and domain_status in {"VERIFIED", "ACTIVE"}:
            domain = tenant.custom_domain.strip().rstrip("/")
            if domain.startswith(("https://", "http://")):
                safe_domain = _safe_http_base_url(domain)
            else:
                safe_domain = _safe_http_base_url(f"https://{domain}")
            if safe_domain:
                return safe_domain

        configured_url = _safe_http_base_url(
            (tenant.settings or {}).get("frontend_url")
        )
        if configured_url:
            return configured_url

    fallback = _safe_http_base_url(settings.FRONTEND_URL)
    if fallback:
        return fallback

    # FRONTEND_URL is application-controlled configuration. If it is malformed,
    # fail closed to a harmless relative base rather than emitting javascript:,
    # credentials-in-URL, or another unsafe scheme in transactional email HTML.
    logger.error("Invalid FRONTEND_URL configured for transactional email links")
    return ""


async def send_welcome_notification(
    db: AsyncSession,
    user: User,
    tenant_id: UUID,
) -> bool:
    """Send the public-registration welcome email without affecting registration."""
    if not _email_enabled():
        return False

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
    if not _email_enabled():
        return False

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
