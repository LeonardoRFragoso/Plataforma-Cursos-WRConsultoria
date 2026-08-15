import uuid
from datetime import timedelta

import pytest

from app.api.routes.reports import export_data
from app.core.constants import WR_TENANT_ID
from app.core.context import current_tenant_id
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.core.utils import utc_now
from app.models.certificate import Certificate
from app.models.class_model import Class, ClassStatus
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.student import Student
from app.models.user import User, UserRole
from app.services.export_service import ExportService


def test_export_csv():
    rows = [
        {"id": "1", "name": "Alice", "value": 10.5},
        {"id": "2", "name": "Bob", "value": 20.0},
    ]
    content = ExportService.to_csv(rows, ["id", "name", "value"])
    text = content.decode("utf-8-sig")
    assert "id,name,value" in text
    assert "Alice" in text
    assert "Bob" in text


def test_export_xlsx():
    rows = [
        {"id": "1", "name": "Alice", "value": 10.5},
        {"id": "2", "name": "Bob", "value": 20.0},
    ]
    content = ExportService.to_xlsx(rows, ["id", "name", "value"])
    assert content.startswith(b"PK")


def test_export_empty_csv():
    content = ExportService.to_csv([], ["id", "name"])
    text = content.decode("utf-8-sig")
    assert "id,name" in text


def test_export_empty_xlsx():
    content = ExportService.to_xlsx([], ["id", "name"])
    assert content.startswith(b"PK")


@pytest.mark.asyncio
async def test_export_students_csv():
    token = current_tenant_id.set(WR_TENANT_ID)
    try:
        async with AsyncSessionLocal() as db:
            db.info["tenant_id"] = WR_TENANT_ID

            user = User(
                email="student-export@test.com",
                full_name="Student Export",
                password_hash=hash_password("student123"),
                role=UserRole.STUDENT,
                is_active=True,
                tenant_id=WR_TENANT_ID,
            )
            db.add(user)
            await db.flush()

            student = Student(
                user_id=user.id,
                cpf="52988744005",
                phone="(11) 99999-9999",
                tenant_id=WR_TENANT_ID,
            )
            db.add(student)
            await db.commit()

        async with AsyncSessionLocal() as db:
            db.info["tenant_id"] = WR_TENANT_ID
            response = await export_data(
                "students",
                "csv",
                db,
                {"user_id": str(user.id), "role": "admin"},
            )
            assert response.media_type == "text/csv; charset=utf-8"
            body = b"".join([chunk async for chunk in response.body_iterator])
            assert b"52988744005" in body
    finally:
        current_tenant_id.reset(token)


async def _seed_certificate_data():
    """Cria curso, admin, turma, aluno, matrícula concluída e certificado."""
    today = utc_now().date()
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID

        admin = User(
            email=f"admin_{uuid.uuid4().hex[:6]}@test.com",
            full_name="Admin Cert",
            password_hash=hash_password("admin123"),
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(admin)

        student_user = User(
            email=f"student_{uuid.uuid4().hex[:6]}@test.com",
            full_name="Student Cert",
            password_hash=hash_password("student123"),
            role=UserRole.STUDENT,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(student_user)

        course = Course(
            code=f"C-{uuid.uuid4().hex[:6].upper()}",
            name="Curso Cert Export",
            category="Segurança",
            carga_horaria=40,
            modality="PRESENCIAL",
            price=200.0,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(course)
        await db.flush()

        cls = Class(
            course_id=course.id,
            responsible_admin_id=admin.id,
            start_date=today - timedelta(days=60),
            end_date=today - timedelta(days=30),
            max_students=20,
            status=ClassStatus.CONCLUIDA,
            tenant_id=WR_TENANT_ID,
        )
        db.add(cls)

        student = Student(
            user_id=student_user.id,
            cpf="52998744005",
            phone="(11) 99999-9999",
            tenant_id=WR_TENANT_ID,
        )
        db.add(student)
        await db.flush()

        enrollment = Enrollment(
            student_id=student.id,
            class_id=cls.id,
            price=200.0,
            status=EnrollmentStatus.CONCLUIDA,
            tenant_id=WR_TENANT_ID,
        )
        db.add(enrollment)
        await db.flush()

        certificate = Certificate(
            enrollment_id=enrollment.id,
            certificate_number=f"CERT-{uuid.uuid4().hex[:8].upper()}",
            validation_code=uuid.uuid4().hex,
            tenant_id=WR_TENANT_ID,
        )
        db.add(certificate)
        await db.commit()
        await db.refresh(certificate)
        return certificate.certificate_number, certificate.validation_code, admin.id


@pytest.mark.asyncio
async def test_export_certificates_csv():
    cert_number, validation_code, admin_id = await _seed_certificate_data()

    token = current_tenant_id.set(WR_TENANT_ID)
    try:
        async with AsyncSessionLocal() as db:
            db.info["tenant_id"] = WR_TENANT_ID
            response = await export_data(
                "certificates",
                "csv",
                db,
                {"user_id": str(admin_id), "role": "admin"},
            )
            assert response.media_type == "text/csv; charset=utf-8"
            body = b"".join([chunk async for chunk in response.body_iterator])
            text = body.decode("utf-8-sig")
            assert "certificate_number" in text
            assert cert_number in text
            assert validation_code in text
            assert "validation_code" in text
    finally:
        current_tenant_id.reset(token)


@pytest.mark.asyncio
async def test_export_certificates_xlsx():
    _cert_number, _, admin_id = await _seed_certificate_data()

    token = current_tenant_id.set(WR_TENANT_ID)
    try:
        async with AsyncSessionLocal() as db:
            db.info["tenant_id"] = WR_TENANT_ID
            response = await export_data(
                "certificates",
                "xlsx",
                db,
                {"user_id": str(admin_id), "role": "admin"},
            )
            assert (
                response.media_type
                == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            body = b"".join([chunk async for chunk in response.body_iterator])
            assert body.startswith(b"PK")  # XLSX zip signature
    finally:
        current_tenant_id.reset(token)


@pytest.mark.asyncio
async def test_export_certificates_invalid_format():
    _, _, admin_id = await _seed_certificate_data()

    from fastapi import HTTPException

    token = current_tenant_id.set(WR_TENANT_ID)
    try:
        async with AsyncSessionLocal() as db:
            db.info["tenant_id"] = WR_TENANT_ID
            with pytest.raises(HTTPException) as exc:
                await export_data(
                    "certificates",
                    "pdf",
                    db,
                    {"user_id": str(admin_id), "role": "admin"},
                )
            assert exc.value.status_code == 400
            assert "format" in exc.value.detail.lower()
    finally:
        current_tenant_id.reset(token)


@pytest.mark.asyncio
async def test_export_certificates_tenant_isolation():
    """Certificados do tenant WR não vazam para outro tenant."""
    cert_number, _, admin_id = await _seed_certificate_data()
    other_tenant_id = uuid.uuid4()

    token = current_tenant_id.set(other_tenant_id)
    try:
        async with AsyncSessionLocal() as db:
            db.info["tenant_id"] = other_tenant_id
            response = await export_data(
                "certificates",
                "csv",
                db,
                {"user_id": str(admin_id), "role": "admin"},
            )
            body = b"".join([chunk async for chunk in response.body_iterator])
            text = body.decode("utf-8-sig")
            assert cert_number not in text
    finally:
        current_tenant_id.reset(token)
