"""Event-level tests for email mock mode and email disabled.

Verifies at the EVENT level (not just EmailService unit level) that:
1. EMAIL_MOCK_MODE=true → zero SMTP external calls
2. EMAIL_ENABLED=false → zero email attempts
3. Real event flow (payment approved) respects mock mode
"""

from __future__ import annotations

import uuid

import pytest

from app.core.config import settings
from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.core.utils import utc_now
from app.models.class_model import Class, ClassStatus
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.student import Student
from app.models.user import User, UserRole
from app.services.email_service import get_email_service, reset_email_service
from app.services.transactional_notifications import (
    send_certificate_issued_notification,
    send_course_completed_notification,
    send_payment_approved_notification,
)


async def _seed_enrollment():
    """Seed a complete enrollment for testing."""
    today = utc_now().date()
    async with AsyncSessionLocal() as db:
        user = User(
            tenant_id=WR_TENANT_ID,
            email=f"evt-{uuid.uuid4().hex[:8]}@example.com",
            full_name="Aluno Event Test",
            cpf="52998224725",
            password_hash=hash_password("student123"),
            role=UserRole.STUDENT,
            is_active=True,
        )
        admin = User(
            tenant_id=WR_TENANT_ID,
            email=f"evt-admin-{uuid.uuid4().hex[:8]}@example.com",
            full_name="Admin Event Test",
            cpf="11122233344",
            password_hash=hash_password("admin123"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        course = Course(
            tenant_id=WR_TENANT_ID,
            code=f"EVT-{uuid.uuid4().hex[:6].upper()}",
            name="Curso Event Test",
            category="Segurança",
            carga_horaria=8,
            modality="EAD",
            price=150.0,
            is_active=True,
        )
        db.add_all([user, admin, course])
        await db.flush()

        student = Student(tenant_id=WR_TENANT_ID, user_id=user.id, cpf=user.cpf)
        class_obj = Class(
            tenant_id=WR_TENANT_ID,
            course_id=course.id,
            responsible_admin_id=admin.id,
            start_date=today,
            end_date=today,
            max_students=20,
            status=ClassStatus.ABERTA,
        )
        db.add_all([student, class_obj])
        await db.flush()

        enrollment = Enrollment(
            tenant_id=WR_TENANT_ID,
            student_id=student.id,
            class_id=class_obj.id,
            price=150.0,
            status=EnrollmentStatus.CONCLUIDA,
        )
        db.add(enrollment)
        await db.commit()
        return enrollment.id


@pytest.mark.asyncio
async def test_email_mock_mode_no_smtp_calls(monkeypatch):
    """EMAIL_MOCK_MODE=true → zero SMTP external calls at event level."""
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_MOCK_MODE", True)
    reset_email_service()

    enrollment_id = await _seed_enrollment()
    payment_id = uuid.uuid4()

    async with AsyncSessionLocal() as db:
        enrollment = await db.get(Enrollment, enrollment_id)
        result = await send_payment_approved_notification(
            db, enrollment, amount="150.00", payment_method="PIX", payment_id=payment_id
        )
        await db.commit()

    # Email was "sent" (mock) but no real SMTP
    assert result is True
    emails = get_email_service().sent_emails
    assert len(emails) == 1
    # Verify the email service is in mock mode
    assert get_email_service()._mock is True


@pytest.mark.asyncio
async def test_email_disabled_zero_attempts(monkeypatch):
    """EMAIL_ENABLED=false → zero email attempts at event level."""
    monkeypatch.setattr(settings, "EMAIL_ENABLED", False)
    monkeypatch.setattr(settings, "EMAIL_MOCK_MODE", True)
    reset_email_service()

    enrollment_id = await _seed_enrollment()
    payment_id = uuid.uuid4()

    async with AsyncSessionLocal() as db:
        enrollment = await db.get(Enrollment, enrollment_id)
        result = await send_payment_approved_notification(
            db, enrollment, amount="150.00", payment_method="PIX", payment_id=payment_id
        )
        await db.commit()

    # No email should be sent
    assert result is False
    emails = get_email_service().sent_emails
    assert len(emails) == 0


@pytest.mark.asyncio
async def test_course_completed_event_mock_mode(monkeypatch):
    """Course completed event in mock mode → email logged, not sent via SMTP."""
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_MOCK_MODE", True)
    reset_email_service()

    enrollment_id = await _seed_enrollment()

    async with AsyncSessionLocal() as db:
        enrollment = await db.get(Enrollment, enrollment_id)
        result = await send_course_completed_notification(
            db, enrollment, certificate_url="https://example.com/cert/123"
        )
        await db.commit()

    assert result is True
    emails = get_email_service().sent_emails
    assert len(emails) == 1
    assert get_email_service()._mock is True


@pytest.mark.asyncio
async def test_certificate_issued_event_mock_mode(monkeypatch):
    """Certificate issued event in mock mode → email logged, not sent via SMTP."""
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_MOCK_MODE", True)
    reset_email_service()

    enrollment_id = await _seed_enrollment()

    async with AsyncSessionLocal() as db:
        enrollment = await db.get(Enrollment, enrollment_id)
        result = await send_certificate_issued_notification(
            db,
            enrollment,
            certificate_number="CERT-EVT-123",
            validation_code="VALID-EVT-123",
        )
        await db.commit()

    assert result is True
    emails = get_email_service().sent_emails
    assert len(emails) == 1
    assert get_email_service()._mock is True


@pytest.mark.asyncio
async def test_email_disabled_blocks_all_event_types(monkeypatch):
    """EMAIL_ENABLED=false blocks all notification types at event level."""
    monkeypatch.setattr(settings, "EMAIL_ENABLED", False)
    monkeypatch.setattr(settings, "EMAIL_MOCK_MODE", True)
    reset_email_service()

    enrollment_id = await _seed_enrollment()

    async with AsyncSessionLocal() as db:
        enrollment = await db.get(Enrollment, enrollment_id)

        r1 = await send_payment_approved_notification(
            db, enrollment, amount="150.00", payment_method="PIX",
            payment_id=uuid.uuid4(),
        )
        r2 = await send_course_completed_notification(
            db, enrollment, certificate_url="https://example.com",
        )
        r3 = await send_certificate_issued_notification(
            db, enrollment, certificate_number="CERT-123",
            validation_code="VALID-123",
        )
        await db.commit()

    assert r1 is False
    assert r2 is False
    assert r3 is False
    emails = get_email_service().sent_emails
    assert len(emails) == 0
