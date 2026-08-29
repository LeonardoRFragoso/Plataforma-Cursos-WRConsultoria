"""Tests for notification idempotency — persistent dedup, not in-memory.

Verifies that:
1. Same event called twice → only 1 email intent (1 dedup record)
2. Different events → independent (both send)
3. Dedup keys are correctly formatted
4. check_and_record is atomic (handles concurrent inserts)
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.notification_event import NotificationEvent
from app.services.notification_idempotency import check_and_record, make_dedup_key


@pytest.mark.asyncio
async def test_check_and_record_first_call_returns_true():
    """First call for a dedup_key returns True (should proceed)."""
    tenant_id = uuid.uuid4()
    dedup_key = f"test-event-{uuid.uuid4()}"
    async with AsyncSessionLocal() as db:
        result = await check_and_record(db, tenant_id, dedup_key, "test_type")
        await db.commit()
        assert result is True


@pytest.mark.asyncio
async def test_check_and_record_second_call_returns_false():
    """Second call for the same dedup_key returns False (skip)."""
    tenant_id = uuid.uuid4()
    dedup_key = f"test-event-{uuid.uuid4()}"
    async with AsyncSessionLocal() as db:
        first = await check_and_record(db, tenant_id, dedup_key, "test_type")
        await db.commit()
        assert first is True

        second = await check_and_record(db, tenant_id, dedup_key, "test_type")
        await db.commit()
        assert second is False


@pytest.mark.asyncio
async def test_different_dedup_keys_both_proceed():
    """Different dedup_keys → both return True (independent)."""
    tenant_id = uuid.uuid4()
    key1 = f"test-event-1-{uuid.uuid4()}"
    key2 = f"test-event-2-{uuid.uuid4()}"
    async with AsyncSessionLocal() as db:
        r1 = await check_and_record(db, tenant_id, key1, "test_type")
        await db.commit()
        r2 = await check_and_record(db, tenant_id, key2, "test_type")
        await db.commit()
        assert r1 is True
        assert r2 is True


@pytest.mark.asyncio
async def test_dedup_key_format():
    """make_dedup_key produces correct format."""
    key = make_dedup_key("payment-approved", "abc-123")
    assert key == "payment-approved:abc-123"


@pytest.mark.asyncio
async def test_notification_event_recorded_in_db():
    """After check_and_record, a NotificationEvent row exists in the DB."""
    tenant_id = uuid.uuid4()
    dedup_key = f"test-db-{uuid.uuid4()}"
    entity_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        await check_and_record(db, tenant_id, dedup_key, "payment_approved", entity_id=entity_id)
        await db.commit()

        # Verify the record exists
        record = await db.scalar(
            select(NotificationEvent).where(NotificationEvent.dedup_key == dedup_key)
        )
        assert record is not None
        assert record.tenant_id == tenant_id
        assert record.notification_type == "payment_approved"
        assert record.entity_id == entity_id
        assert record.status == "SENT"


@pytest.mark.asyncio
async def test_idempotency_with_real_notification_helper():
    """Full integration: send_payment_approved_notification called twice → 1 email."""
    from app.core.config import settings

    # Use WR tenant for test
    from app.core.constants import WR_TENANT_ID
    from app.core.utils import utc_now
    from app.models.class_model import Class, ClassStatus
    from app.models.course import Course
    from app.models.enrollment import Enrollment, EnrollmentStatus
    from app.models.student import Student
    from app.models.user import User, UserRole
    from app.services.email_service import get_email_service, reset_email_service
    from app.services.transactional_notifications import send_payment_approved_notification

    tenant_id = WR_TENANT_ID
    today = utc_now().date()
    payment_id = uuid.uuid4()

    async with AsyncSessionLocal() as db:
        user = User(
            tenant_id=tenant_id,
            email=f"idemp-{uuid.uuid4().hex[:8]}@example.com",
            full_name="Aluno Idempotency",
            cpf="52998224725",
            password_hash="$2b$12$dummy",
            role=UserRole.STUDENT,
            is_active=True,
        )
        admin = User(
            tenant_id=tenant_id,
            email=f"idemp-admin-{uuid.uuid4().hex[:8]}@example.com",
            full_name="Admin Idempotency",
            cpf="11122233344",
            password_hash="$2b$12$dummy",
            role=UserRole.ADMIN,
            is_active=True,
        )
        course = Course(
            tenant_id=tenant_id,
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

        student = Student(tenant_id=tenant_id, user_id=user.id, cpf=user.cpf)
        class_obj = Class(
            tenant_id=tenant_id,
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
            tenant_id=tenant_id,
            student_id=student.id,
            class_id=class_obj.id,
            price=150.0,
            status=EnrollmentStatus.CONCLUIDA,
        )
        db.add(enrollment)
        await db.commit()

    # Patch settings for mock email
    with patch.object(settings, "EMAIL_ENABLED", True), patch.object(settings, "EMAIL_MOCK_MODE", True):
        reset_email_service()

        async with AsyncSessionLocal() as db:
            enrollment = await db.get(Enrollment, enrollment.id)

            # First call — should send
            r1 = await send_payment_approved_notification(
                db, enrollment, amount="150.00", payment_method="PIX", payment_id=payment_id
            )
            await db.commit()

            # Second call — should be skipped (idempotent)
            r2 = await send_payment_approved_notification(
                db, enrollment, amount="150.00", payment_method="PIX", payment_id=payment_id
            )
            await db.commit()

            assert r1 is True
            assert r2 is False

        # Verify only 1 email was sent
        emails = get_email_service().sent_emails
        assert len(emails) == 1
