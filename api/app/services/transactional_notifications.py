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
from app.services.notification_idempotency import make_dedup_key, mark_failed, mark_sent, reserve

logger = logging.getLogger(__name__)


def _email_enabled() -> bool:
    """Honor the explicit production email switch when present."""
    return bool(getattr(settings, "EMAIL_ENABLED", True))


def _safe_http_base_url(value: str | None) -> str | None:
    """Accept only absolute, credential-free HTTP(S) URLs for email links."""
    if not value:
        return None

    candidate = str(value).strip().rstrip("/")
    if any(char in candidate for char in ("\r", "\n", "\t")):
        return None

    try:
        parsed = urlsplit(candidate)
        hostname = parsed.hostname
        # Accessing port validates malformed values such as ``host:not-a-port``.
        _ = parsed.port
    except ValueError:
        return None

    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not hostname:
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


async def send_payment_approved_notification(
    db: AsyncSession,
    enrollment: Enrollment,
    *,
    amount: str,
    payment_method: str,
    payment_id: UUID | None = None,
) -> bool:
    """Notify a student that their payment has been approved.

    Idempotent state machine:
    - reserve(dedup_key) → PENDING in isolated session
    - send email
    - success → mark_sent → SENT
    - failure → mark_failed → FAILED (retryable)
    The caller's session is NEVER touched by the idempotency service.
    """
    if not _email_enabled():
        return False
    # Idempotency: reserve dedup key in isolated session
    if payment_id is not None:
        dedup_key = make_dedup_key("payment-approved", payment_id)
        if not await reserve(enrollment.tenant_id, dedup_key, "payment_approved", entity_id=payment_id):
            return False
    else:
        dedup_key = None
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
            if dedup_key:
                await mark_failed(dedup_key)
            return False
        user, course, tenant = row
        frontend_url = _tenant_frontend_url(tenant)
        course_url = f"{frontend_url}/courses/{course.id}/learn"
        result = await get_email_service().send_payment_approved(
            to=user.email,
            full_name=user.full_name,
            course_name=course.name,
            amount=amount,
            payment_method=payment_method,
            course_url=course_url,
            tenant_name=tenant.name,
        )
        if dedup_key:
            if result is True:
                await mark_sent(dedup_key)
            else:
                await mark_failed(dedup_key)
        return result
    except EmailServiceError:
        logger.warning("Payment-approved email failed for enrollment %s", enrollment.id)
        if dedup_key:
            await mark_failed(dedup_key)
    except Exception:
        logger.exception("Unexpected payment-approved notification failure for enrollment %s", enrollment.id)
        if dedup_key:
            await mark_failed(dedup_key)
    return False


async def send_course_completed_notification(
    db: AsyncSession,
    enrollment: Enrollment,
    *,
    certificate_url: str | None = None,
) -> bool:
    """Notify a student that their course has been completed.

    Idempotent state machine: reserve → send → mark_sent/mark_failed.
    The caller's session is NEVER touched by the idempotency service.
    """
    if not _email_enabled():
        return False
    # Idempotency: reserve dedup key in isolated session
    dedup_key = make_dedup_key("course-completed", enrollment.id)
    if not await reserve(enrollment.tenant_id, dedup_key, "course_completed", entity_id=enrollment.id):
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
            await mark_failed(dedup_key)
            return False
        user, course, tenant = row
        result = await get_email_service().send_course_completed(
            to=user.email,
            full_name=user.full_name,
            course_name=course.name,
            certificate_url=certificate_url,
            tenant_name=tenant.name,
        )
        if result is True:
            await mark_sent(dedup_key)
        else:
            await mark_failed(dedup_key)
        return result
    except EmailServiceError:
        logger.warning("Course-completed email failed for enrollment %s", enrollment.id)
        await mark_failed(dedup_key)
    except Exception:
        logger.exception("Unexpected course-completed notification failure for enrollment %s", enrollment.id)
        await mark_failed(dedup_key)
    return False


async def send_certificate_issued_notification(
    db: AsyncSession,
    enrollment: Enrollment,
    *,
    certificate_number: str,
    validation_code: str,
    certificate_id: UUID | None = None,
) -> bool:
    """Notify a student that their certificate has been issued.

    Idempotent state machine: reserve → send → mark_sent/mark_failed.
    The caller's session is NEVER touched by the idempotency service.
    """
    if not _email_enabled():
        return False
    # Idempotency: reserve dedup key in isolated session
    cert_key = certificate_id or enrollment.id
    dedup_key = make_dedup_key("certificate-issued", cert_key)
    if not await reserve(enrollment.tenant_id, dedup_key, "certificate_issued", entity_id=cert_key):
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
            await mark_failed(dedup_key)
            return False
        user, course, tenant = row
        frontend_url = _tenant_frontend_url(tenant)
        validation_url = f"{frontend_url}/validar-certificado?codigo={validation_code}"
        result = await get_email_service().send_certificate_issued(
            to=user.email,
            full_name=user.full_name,
            course_name=course.name,
            certificate_number=certificate_number,
            validation_url=validation_url,
            tenant_name=tenant.name,
        )
        if result is True:
            await mark_sent(dedup_key)
        else:
            await mark_failed(dedup_key)
        return result
    except EmailServiceError:
        logger.warning("Certificate-issued email failed for enrollment %s", enrollment.id)
        await mark_failed(dedup_key)
    except Exception:
        logger.exception("Unexpected certificate-issued notification failure for enrollment %s", enrollment.id)
        await mark_failed(dedup_key)
    return False


async def send_certificate_expiration_notification(
    db: AsyncSession,
    *,
    enrollment_id: UUID,
    tenant_id: UUID,
    certificate_number: str,
    expires_at: str,
    certificate_id: UUID | None = None,
    window: str = "30d",
) -> bool:
    """Warn a student that their certificate is nearing expiration.

    Idempotent state machine: reserve → send → mark_sent/mark_failed.
    The caller's session is NEVER touched by the idempotency service.
    """
    if not _email_enabled():
        return False
    # Idempotency: reserve dedup key in isolated session
    cert_key = certificate_id or enrollment_id
    dedup_key = f"certificate-expiration:{cert_key}:{window}"
    if not await reserve(tenant_id, dedup_key, "certificate_expiration", entity_id=cert_key):
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
                Enrollment.id == enrollment_id,
                Enrollment.tenant_id == tenant_id,
                Student.tenant_id == tenant_id,
                User.tenant_id == tenant_id,
                Class.tenant_id == tenant_id,
                Course.tenant_id == tenant_id,
            )
        )
        row = (await db.execute(stmt)).first()
        if not row:
            await mark_failed(dedup_key)
            return False
        user, course, tenant = row
        result = await get_email_service().send_certificate_expiration_warning(
            to=user.email,
            full_name=user.full_name,
            course_name=course.name,
            certificate_number=certificate_number,
            expires_at=expires_at,
            tenant_name=tenant.name,
        )
        if result is True:
            await mark_sent(dedup_key)
        else:
            await mark_failed(dedup_key)
        return result
    except EmailServiceError:
        logger.warning("Certificate-expiration email failed for enrollment %s", enrollment_id)
        await mark_failed(dedup_key)
    except Exception:
        logger.exception("Unexpected certificate-expiration notification failure for enrollment %s", enrollment_id)
        await mark_failed(dedup_key)
    return False
