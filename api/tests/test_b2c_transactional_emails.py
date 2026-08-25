import uuid
from datetime import timedelta

import pytest

from app.core.config import settings
from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.core.utils import utc_now
from app.models.class_model import Class, ClassStatus
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.student import Student
from app.models.user import User, UserRole
from app.services.email_service import EmailService, get_email_service, reset_email_service
from app.services.payment_reconciliation import reconcile_payment_status
from app.services.transactional_notifications import send_course_access_notification


@pytest.mark.asyncio
async def test_public_registration_sends_welcome_without_password(client, monkeypatch):
    """B2C registration sends one tenant-aware welcome message after commit."""
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_MOCK_MODE", True)
    reset_email_service()

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "welcome-b2c@example.com",
            "full_name": "Aluno Welcome",
            "password": "SecretPassword123!",
            "cpf": "52998224725",
        },
    )

    assert response.status_code == 200
    emails = get_email_service().sent_emails
    assert len(emails) == 1
    assert emails[0]["to"] == "welcome-b2c@example.com"
    assert "Bem-vindo" in emails[0]["subject"]
    assert "SecretPassword123!" not in emails[0]["html_body"]
    assert "SecretPassword123!" not in (emails[0]["text_body"] or "")
    assert "/cursos" in emails[0]["html_body"]


@pytest.mark.asyncio
async def test_email_templates_cover_welcome_and_course_access():
    service = EmailService(mock=True)

    assert await service.send_welcome(
        to="student@example.com",
        full_name="Aluno Teste",
        frontend_url="https://academy.example.com",
        tenant_name="Academia Teste",
    )
    assert await service.send_course_access(
        to="student@example.com",
        full_name="Aluno Teste",
        course_name="NR-10",
        course_url="https://academy.example.com/courses/abc/learn",
        tenant_name="Academia Teste",
    )

    assert len(service.sent_emails) == 2
    assert "Bem-vindo" in service.sent_emails[0]["subject"]
    assert "Curso liberado" in service.sent_emails[1]["subject"]
    assert "Acessar meu curso" in service.sent_emails[1]["html_body"]
    assert "/courses/abc/learn" in service.sent_emails[1]["html_body"]


async def _seed_pending_payment():
    today = utc_now().date()
    async with AsyncSessionLocal() as db:
        user = User(
            tenant_id=WR_TENANT_ID,
            email=f"notify-{uuid.uuid4().hex[:8]}@example.com",
            full_name="Aluno Notificação",
            cpf="52998224725",
            password_hash=hash_password("student123"),
            role=UserRole.STUDENT,
            is_active=True,
        )
        admin = User(
            tenant_id=WR_TENANT_ID,
            email=f"notify-admin-{uuid.uuid4().hex[:8]}@example.com",
            full_name="Admin Notificação",
            cpf="11122233344",
            password_hash=hash_password("admin123"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        course = Course(
            tenant_id=WR_TENANT_ID,
            code=f"NOTIFY-{uuid.uuid4().hex[:6].upper()}",
            name="Curso Notificação",
            category="Segurança",
            carga_horaria=8,
            modality="EAD",
            price=150.0,
            is_active=True,
        )
        db.add_all([user, admin, course])
        await db.flush()

        student = Student(
            tenant_id=WR_TENANT_ID,
            user_id=user.id,
            cpf=user.cpf,
        )
        class_obj = Class(
            tenant_id=WR_TENANT_ID,
            course_id=course.id,
            responsible_admin_id=admin.id,
            start_date=today,
            end_date=today + timedelta(days=30),
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
            status=EnrollmentStatus.PENDENTE,
        )
        db.add(enrollment)
        await db.flush()

        payment = Payment(
            tenant_id=WR_TENANT_ID,
            enrollment_id=enrollment.id,
            amount=150.0,
            status=PaymentStatus.PROCESSANDO,
            method=PaymentMethod.PIX,
        )
        db.add(payment)
        await db.commit()
        return payment.id, enrollment.id


@pytest.mark.asyncio
async def test_course_access_notification_is_triggered_only_on_first_unlock(monkeypatch):
    """Repeated provider approvals cannot generate duplicate unlock emails."""
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_MOCK_MODE", True)
    reset_email_service()
    payment_id, enrollment_id = await _seed_pending_payment()

    async with AsyncSessionLocal() as db:
        payment = await db.get(Payment, payment_id)
        enrollment = await db.get(Enrollment, enrollment_id)

        first = await reconcile_payment_status(
            payment,
            enrollment,
            PaymentStatus.APROVADO,
        )
        await db.commit()
        assert first["enrollment_newly_confirmed"] is True
        assert await send_course_access_notification(db, enrollment) is True

        second = await reconcile_payment_status(
            payment,
            enrollment,
            PaymentStatus.APROVADO,
        )
        await db.commit()
        assert second["idempotent"] is True
        assert second["enrollment_confirmed"] is True
        assert second["enrollment_newly_confirmed"] is False

    emails = get_email_service().sent_emails
    assert len(emails) == 1
    assert emails[0]["to"].startswith("notify-")
    assert "Curso liberado" in emails[0]["subject"]
    assert "/learn" in emails[0]["html_body"]
