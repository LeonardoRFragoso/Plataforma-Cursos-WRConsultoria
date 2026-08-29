"""A/B tenant isolation tests for transactional notification helpers.

Verifies that notification helpers NEVER compose emails with cross-tenant data.
Scenario: tenant A enrollment + tenant B student/user/course → no email sent.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.core.utils import utc_now
from app.models.class_model import Class, ClassStatus
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.student import Student
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.services.email_service import reset_email_service
from app.services.transactional_notifications import (
    send_certificate_issued_notification,
    send_course_completed_notification,
    send_payment_approved_notification,
)


async def _seed_cross_tenant_scenario():
    """Seed enrollment in tenant A with student/user/course in tenant B.

    This creates an inconsistent state where:
    - Enrollment belongs to tenant A
    - Student, User, Class, Course belong to tenant B

    The notification helpers must detect this via tenant_id filters
    and refuse to send (return False, no email composed).
    """
    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()
    today = utc_now().date()

    async with AsyncSessionLocal() as db:
        # Create both tenants first (FK constraint)
        tenant_a = Tenant(
            id=tenant_a_id,
            name="Tenant A Cross",
            slug=f"tenant-a-cross-{uuid.uuid4().hex[:6]}",
            contact_name="Contact A",
            contact_email="a@example.com",
        )
        tenant_b = Tenant(
            id=tenant_b_id,
            name="Tenant B Cross",
            slug=f"tenant-b-cross-{uuid.uuid4().hex[:6]}",
            contact_name="Contact B",
            contact_email="b@example.com",
        )
        db.add_all([tenant_a, tenant_b])
        await db.flush()

        # Tenant B owns the student, user, course, class
        user_b = User(
            tenant_id=tenant_b_id,
            email=f"cross-b-{uuid.uuid4().hex[:8]}@example.com",
            full_name="Aluno Tenant B",
            cpf="52998224725",
            password_hash=hash_password("student123"),
            role=UserRole.STUDENT,
            is_active=True,
        )
        admin_b = User(
            tenant_id=tenant_b_id,
            email=f"cross-admin-b-{uuid.uuid4().hex[:8]}@example.com",
            full_name="Admin Tenant B",
            cpf="11122233344",
            password_hash=hash_password("admin123"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        course_b = Course(
            tenant_id=tenant_b_id,
            code=f"CROSS-B-{uuid.uuid4().hex[:6].upper()}",
            name="Curso Tenant B",
            category="Segurança",
            carga_horaria=8,
            modality="EAD",
            price=150.0,
            is_active=True,
        )
        db.add_all([user_b, admin_b, course_b])
        await db.flush()

        student_b = Student(
            tenant_id=tenant_b_id,
            user_id=user_b.id,
            cpf=user_b.cpf,
        )
        class_b = Class(
            tenant_id=tenant_b_id,
            course_id=course_b.id,
            responsible_admin_id=admin_b.id,
            start_date=today,
            end_date=today + timedelta(days=30),
            max_students=20,
            status=ClassStatus.ABERTA,
        )
        db.add_all([student_b, class_b])
        await db.flush()

        # Tenant A enrollment pointing to tenant B's student/class
        # (This is an inconsistent state that should never happen via
        # normal operations, but we test the defense-in-depth filter)
        enrollment_a = Enrollment(
            tenant_id=tenant_a_id,
            student_id=student_b.id,
            class_id=class_b.id,
            price=150.0,
            status=EnrollmentStatus.CONCLUIDA,
        )
        db.add(enrollment_a)
        await db.commit()
        return enrollment_a.id, tenant_a_id


@pytest.mark.asyncio
async def test_payment_approved_notification_cross_tenant_no_email(monkeypatch):
    """Tenant A enrollment + tenant B student/user/course → no email."""
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_MOCK_MODE", True)
    reset_email_service()

    enrollment_id, _tenant_id = await _seed_cross_tenant_scenario()

    async with AsyncSessionLocal() as db:
        enrollment = await db.get(Enrollment, enrollment_id)
        result = await send_payment_approved_notification(
            db,
            enrollment,
            amount="150.00",
            payment_method="PIX",
        )
        # Must return False — cross-tenant data detected
        assert result is False


@pytest.mark.asyncio
async def test_course_completed_notification_cross_tenant_no_email(monkeypatch):
    """Tenant A enrollment + tenant B student/user/course → no email."""
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_MOCK_MODE", True)
    reset_email_service()

    enrollment_id, _tenant_id = await _seed_cross_tenant_scenario()

    async with AsyncSessionLocal() as db:
        enrollment = await db.get(Enrollment, enrollment_id)
        result = await send_course_completed_notification(
            db,
            enrollment,
            certificate_url="https://example.com/cert/123",
        )
        assert result is False


@pytest.mark.asyncio
async def test_certificate_issued_notification_cross_tenant_no_email(monkeypatch):
    """Tenant A enrollment + tenant B student/user/course → no email."""
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_MOCK_MODE", True)
    reset_email_service()

    enrollment_id, _tenant_id = await _seed_cross_tenant_scenario()

    async with AsyncSessionLocal() as db:
        enrollment = await db.get(Enrollment, enrollment_id)
        result = await send_certificate_issued_notification(
            db,
            enrollment,
            certificate_number="CERT-123",
            validation_code="VALID-123",
        )
        assert result is False


@pytest.mark.asyncio
async def test_certificate_expiration_notification_cross_tenant_no_email(monkeypatch):
    """Tenant A enrollment + tenant B student/user/course → no email."""
    from app.services.transactional_notifications import (
        send_certificate_expiration_notification,
    )

    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_MOCK_MODE", True)
    reset_email_service()

    enrollment_id, tenant_id = await _seed_cross_tenant_scenario()

    async with AsyncSessionLocal() as db:
        result = await send_certificate_expiration_notification(
            db,
            enrollment_id=enrollment_id,
            tenant_id=tenant_id,
            certificate_number="CERT-123",
            expires_at="2026-12-31",
        )
        assert result is False
