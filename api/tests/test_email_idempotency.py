"""Real idempotency tests — state machine, isolated session, no caller rollback.

Tests A-H as specified:
A) send succeeds, caller doesn't commit → NotificationEvent SENT persists
B) same event again → zero second email
C) SMTP fails → status FAILED
D) retry after FAILED → can try again
E) retry succeeds → SENT
F) two concurrent calls → only 1 email
G) IntegrityError/conflict → NO rollback of caller's business transaction
H) mock mode → idempotency works
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.core.utils import utc_now
from app.models.class_model import Class, ClassStatus
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.notification_event import NotificationEvent
from app.models.student import Student
from app.models.user import User, UserRole
from app.services.email_service import EmailServiceError, get_email_service, reset_email_service
from app.services.notification_idempotency import (
    STATUS_FAILED,
    STATUS_SENT,
    make_dedup_key,
    mark_failed,
    mark_sent,
    reserve,
)
from app.services.transactional_notifications import (
    send_course_completed_notification,
    send_payment_approved_notification,
)


async def _seed_enrollment():
    """Seed a complete enrollment for testing. Returns enrollment_id."""
    today = utc_now().date()
    async with AsyncSessionLocal() as db:
        user = User(
            tenant_id=WR_TENANT_ID,
            email=f"idemp-{uuid.uuid4().hex[:8]}@example.com",
            full_name="Aluno Idempotency",
            cpf=uuid.uuid4().hex[:11],
            password_hash=hash_password("student123"),
            role=UserRole.STUDENT,
            is_active=True,
        )
        admin = User(
            tenant_id=WR_TENANT_ID,
            email=f"idemp-admin-{uuid.uuid4().hex[:8]}@example.com",
            full_name="Admin Idempotency",
            cpf=uuid.uuid4().hex[:11],
            password_hash=hash_password("admin123"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        course = Course(
            tenant_id=WR_TENANT_ID,
            code=f"IDEMP-{uuid.uuid4().hex[:6].upper()}",
            name="Curso Idempotency",
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
async def test_a_sent_persists_without_caller_commit(monkeypatch):
    """A) send succeeds, caller doesn't commit → NotificationEvent SENT persists."""
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_MOCK_MODE", True)
    reset_email_service()

    enrollment_id = await _seed_enrollment()
    payment_id = uuid.uuid4()

    # Call the helper with a session that we DON'T commit after
    async with AsyncSessionLocal() as db:
        enrollment = await db.get(Enrollment, enrollment_id)
        result = await send_payment_approved_notification(
            db, enrollment, amount="150.00", payment_method="PIX", payment_id=payment_id
        )
        # NOTE: no db.commit() here — simulating real callers that don't commit

    assert result is True

    # Verify NotificationEvent SENT persists in a FRESH session
    async with AsyncSessionLocal() as db:
        event = await db.scalar(
            select(NotificationEvent).where(
                NotificationEvent.dedup_key == make_dedup_key("payment-approved", payment_id)
            )
        )
        assert event is not None
        assert event.status == STATUS_SENT

    # Verify exactly 1 email was sent
    assert len(get_email_service().sent_emails) == 1


@pytest.mark.asyncio
async def test_b_same_event_no_second_email(monkeypatch):
    """B) same event again → zero second email."""
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_MOCK_MODE", True)
    reset_email_service()

    enrollment_id = await _seed_enrollment()
    payment_id = uuid.uuid4()

    async with AsyncSessionLocal() as db:
        enrollment = await db.get(Enrollment, enrollment_id)
        r1 = await send_payment_approved_notification(
            db, enrollment, amount="150.00", payment_method="PIX", payment_id=payment_id
        )

    async with AsyncSessionLocal() as db:
        enrollment = await db.get(Enrollment, enrollment_id)
        r2 = await send_payment_approved_notification(
            db, enrollment, amount="150.00", payment_method="PIX", payment_id=payment_id
        )

    assert r1 is True
    assert r2 is False
    assert len(get_email_service().sent_emails) == 1


@pytest.mark.asyncio
async def test_c_smtp_fail_status_failed(monkeypatch):
    """C) SMTP fails → status FAILED."""
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_MOCK_MODE", True)
    reset_email_service()

    enrollment_id = await _seed_enrollment()
    payment_id = uuid.uuid4()

    # Patch the email service to raise EmailServiceError
    with patch.object(
        get_email_service(),
        "send_payment_approved",
        new_callable=AsyncMock,
        side_effect=EmailServiceError("SMTP connection refused"),
    ):
        async with AsyncSessionLocal() as db:
            enrollment = await db.get(Enrollment, enrollment_id)
            result = await send_payment_approved_notification(
                db, enrollment, amount="150.00", payment_method="PIX", payment_id=payment_id
            )

    assert result is False

    # Verify status is FAILED
    async with AsyncSessionLocal() as db:
        event = await db.scalar(
            select(NotificationEvent).where(
                NotificationEvent.dedup_key == make_dedup_key("payment-approved", payment_id)
            )
        )
        assert event is not None
        assert event.status == STATUS_FAILED

    # No email was sent
    assert len(get_email_service().sent_emails) == 0


@pytest.mark.asyncio
async def test_d_retry_after_failed_can_try_again(monkeypatch):
    """D) retry after FAILED → can try again (reserve returns True)."""
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_MOCK_MODE", True)
    reset_email_service()

    enrollment_id = await _seed_enrollment()
    payment_id = uuid.uuid4()
    dedup_key = make_dedup_key("payment-approved", payment_id)

    # First attempt: fail
    with patch.object(
        get_email_service(),
        "send_payment_approved",
        new_callable=AsyncMock,
        side_effect=EmailServiceError("SMTP down"),
    ):
        async with AsyncSessionLocal() as db:
            enrollment = await db.get(Enrollment, enrollment_id)
            await send_payment_approved_notification(
                db, enrollment, amount="150.00", payment_method="PIX", payment_id=payment_id
            )

    # Verify FAILED
    async with AsyncSessionLocal() as db:
        event = await db.scalar(
            select(NotificationEvent).where(NotificationEvent.dedup_key == dedup_key)
        )
        assert event.status == STATUS_FAILED

    # Second attempt: should be allowed (retry)
    can_retry = await reserve(WR_TENANT_ID, dedup_key, "payment_approved", entity_id=payment_id)
    assert can_retry is True


@pytest.mark.asyncio
async def test_e_retry_succeeds_sent(monkeypatch):
    """E) retry succeeds → SENT."""
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_MOCK_MODE", True)
    reset_email_service()

    enrollment_id = await _seed_enrollment()
    payment_id = uuid.uuid4()

    # First attempt: fail
    with patch.object(
        get_email_service(),
        "send_payment_approved",
        new_callable=AsyncMock,
        side_effect=EmailServiceError("SMTP down"),
    ):
        async with AsyncSessionLocal() as db:
            enrollment = await db.get(Enrollment, enrollment_id)
            await send_payment_approved_notification(
                db, enrollment, amount="150.00", payment_method="PIX", payment_id=payment_id
            )

    # Second attempt: succeed (no patch, uses mock mode)
    async with AsyncSessionLocal() as db:
        enrollment = await db.get(Enrollment, enrollment_id)
        result = await send_payment_approved_notification(
            db, enrollment, amount="150.00", payment_method="PIX", payment_id=payment_id
        )

    assert result is True

    # Verify SENT
    async with AsyncSessionLocal() as db:
        event = await db.scalar(
            select(NotificationEvent).where(
                NotificationEvent.dedup_key == make_dedup_key("payment-approved", payment_id)
            )
        )
        assert event.status == STATUS_SENT

    # Exactly 1 email (from the retry)
    assert len(get_email_service().sent_emails) == 1


@pytest.mark.asyncio
async def test_f_concurrent_calls_one_email(monkeypatch):
    """F) two concurrent calls → only 1 email."""
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_MOCK_MODE", True)
    reset_email_service()

    enrollment_id = await _seed_enrollment()
    payment_id = uuid.uuid4()

    # Run two calls concurrently
    async def _call():
        async with AsyncSessionLocal() as db:
            enrollment = await db.get(Enrollment, enrollment_id)
            return await send_payment_approved_notification(
                db, enrollment, amount="150.00", payment_method="PIX", payment_id=payment_id
            )

    results = await asyncio.gather(_call(), _call())

    # Exactly one should succeed, one should be skipped
    assert results.count(True) == 1
    assert results.count(False) == 1

    # Exactly 1 email
    assert len(get_email_service().sent_emails) == 1

    # Exactly 1 NotificationEvent
    async with AsyncSessionLocal() as db:
        events = (
            await db.execute(
                select(NotificationEvent).where(
                    NotificationEvent.dedup_key == make_dedup_key("payment-approved", payment_id)
                )
            )
        ).scalars().all()
        assert len(events) == 1
        assert events[0].status == STATUS_SENT


@pytest.mark.asyncio
async def test_g_no_caller_rollback(monkeypatch):
    """G) Idempotency conflict → NO rollback of caller's business transaction.

    The idempotency service uses its own session. If it has an internal
    conflict, the caller's session (with business data) must remain intact.
    """
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_MOCK_MODE", True)
    reset_email_service()

    enrollment_id = await _seed_enrollment()
    payment_id = uuid.uuid4()

    # Simulate: caller has uncommitted business data in their session
    async with AsyncSessionLocal() as db:
        enrollment = await db.get(Enrollment, enrollment_id)
        # Modify enrollment (business data)
        enrollment.price = 200.0
        await db.flush()

        # Now call the notification helper — idempotency runs in its own session
        result = await send_payment_approved_notification(
            db, enrollment, amount="200.00", payment_method="PIX", payment_id=payment_id
        )

        # The caller's session should still have the uncommitted change
        # (idempotency service did NOT rollback our session)
        refreshed = await db.get(Enrollment, enrollment_id)
        assert refreshed.price == 200.0

    assert result is True


@pytest.mark.asyncio
async def test_h_mock_mode_idempotency_works(monkeypatch):
    """H) mock mode → idempotency works correctly."""
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_MOCK_MODE", True)
    reset_email_service()

    enrollment_id = await _seed_enrollment()

    async with AsyncSessionLocal() as db:
        enrollment = await db.get(Enrollment, enrollment_id)
        r1 = await send_course_completed_notification(db, enrollment)

    async with AsyncSessionLocal() as db:
        enrollment = await db.get(Enrollment, enrollment_id)
        r2 = await send_course_completed_notification(db, enrollment)

    assert r1 is True
    assert r2 is False
    assert len(get_email_service().sent_emails) == 1

    # Verify SENT status
    async with AsyncSessionLocal() as db:
        event = await db.scalar(
            select(NotificationEvent).where(
                NotificationEvent.dedup_key == make_dedup_key("course-completed", enrollment_id)
            )
        )
        assert event is not None
        assert event.status == STATUS_SENT


@pytest.mark.asyncio
async def test_reserve_atomic_insert_on_conflict():
    """reserve() uses INSERT ON CONFLICT DO NOTHING — atomic, no SELECT-then-INSERT race."""
    tenant_id = uuid.uuid4()
    dedup_key = f"test-atomic-{uuid.uuid4()}"

    r1 = await reserve(tenant_id, dedup_key, "test_type")
    r2 = await reserve(tenant_id, dedup_key, "test_type")

    assert r1 is True
    assert r2 is False


@pytest.mark.asyncio
async def test_mark_sent_updates_status():
    """mark_sent() updates PENDING → SENT in isolated session."""
    tenant_id = uuid.uuid4()
    dedup_key = f"test-marksent-{uuid.uuid4()}"

    await reserve(tenant_id, dedup_key, "test_type")
    await mark_sent(dedup_key)

    async with AsyncSessionLocal() as db:
        event = await db.scalar(
            select(NotificationEvent).where(NotificationEvent.dedup_key == dedup_key)
        )
        assert event.status == STATUS_SENT


@pytest.mark.asyncio
async def test_mark_failed_updates_status():
    """mark_failed() updates PENDING → FAILED in isolated session."""
    tenant_id = uuid.uuid4()
    dedup_key = f"test-markfailed-{uuid.uuid4()}"

    await reserve(tenant_id, dedup_key, "test_type")
    await mark_failed(dedup_key)

    async with AsyncSessionLocal() as db:
        event = await db.scalar(
            select(NotificationEvent).where(NotificationEvent.dedup_key == dedup_key)
        )
        assert event.status == STATUS_FAILED
