"""End-to-end tests for QR certificate validation, demo issuance, journey,
privacy, status differentiation, tenant isolation and content hash.

Covers Phases 26-31 of the certificate QR validation task.
"""

import uuid
from datetime import timedelta

import pytest

from app.core.constants import WR_TENANT_ID
from app.core.context import current_tenant_id
from app.core.database import AsyncSessionLocal
from app.core.utils import utc_now
from app.models.certificate import Certificate
from app.models.class_model import Class, ClassStatus
from app.models.course import Course, CourseModality, CourseType
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.lesson import Lesson, LessonContentType, LessonProgress
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.certificate import (
    CertificateCreate,
    CertificateReissueRequest,
    CertificateRevokeRequest,
)
from app.services.certificate_service import (
    CertificateService,
    build_validation_url,
    is_demo_certificate,
)
from tests.conftest import make_valid_cpf

# -- helpers ---------------------------------------------------------------


async def _setup_course_with_lessons(db, tenant_id, admin_id, *, code=None, n_required=3, validity_days=365):
    code = code or f"QR-{uuid.uuid4().hex[:6].upper()}"
    course = Course(
        tenant_id=tenant_id,
        code=code,
        name=f"Curso QR {code}",
        category="Segurança",
        carga_horaria=8,
        modality=CourseModality.EAD,
        tipo_curso=CourseType.FORMACAO,
        price=100.0,
        certificate_validity_days=validity_days,
    )
    db.add(course)
    await db.flush()
    cls = Class(
        tenant_id=tenant_id,
        course_id=course.id,
        responsible_admin_id=admin_id,
        start_date=utc_now().date(),
        end_date=(utc_now() + timedelta(days=30)).date(),
        max_students=20,
        status=ClassStatus.ABERTA,
    )
    db.add(cls)
    await db.flush()
    lessons = []
    for i in range(n_required):
        lesson = Lesson(
            tenant_id=tenant_id,
            course_id=course.id,
            title=f"Aula {i + 1}",
            order=i,
            content_type=LessonContentType.YOUTUBE,
            duration_seconds=600,
            is_required=True,
        )
        db.add(lesson)
        lessons.append(lesson)
    # one optional lesson to ensure it is NOT counted in required total
    opt = Lesson(
        tenant_id=tenant_id,
        course_id=course.id,
        title="Aula bônus",
        order=n_required,
        content_type=LessonContentType.YOUTUBE,
        duration_seconds=300,
        is_required=False,
    )
    db.add(opt)
    await db.flush()
    return course, cls, lessons


async def _setup_student(db, tenant_id, *, name="Aluno QR Teste"):
    email = f"qrstudent_{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        tenant_id=tenant_id,
        email=email,
        full_name=name,
        cpf=make_valid_cpf(),
        role=UserRole.STUDENT,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    student = Student(
        tenant_id=tenant_id,
        user_id=user.id,
        cpf=make_valid_cpf(),
    )
    db.add(student)
    await db.flush()
    return user, student


async def _complete_enrollment_with_progress(db, tenant_id, student, cls, lessons):
    enrollment = Enrollment(
        tenant_id=tenant_id,
        student_id=student.id,
        class_id=cls.id,
        status=EnrollmentStatus.CONCLUIDA,
        price=100.0,
    )
    db.add(enrollment)
    await db.flush()
    for lesson in lessons:
        db.add(
            LessonProgress(
                tenant_id=tenant_id,
                student_id=student.id,
                lesson_id=lesson.id,
                watched_seconds=600,
                completed=True,
                completed_at=utc_now(),
            )
        )
    await db.flush()
    return enrollment


# -- Phase 2: validation URL ----------------------------------------------


def test_validation_url_uses_public_route():
    url = build_validation_url("https://app.wr.example.com/", "ABC123")
    assert url == "https://app.wr.example.com/validar-certificado?codigo=ABC123"


def test_validation_url_no_personal_data():
    url = build_validation_url("https://app.example.com", "CODE")
    # URL must contain only the validation code, never personal data
    assert "cpf" not in url.lower()
    assert "email" not in url.lower()
    assert "nome" not in url.lower()
    assert "user" not in url.lower()


# -- Phase 3 & 26: QR code generation + decode ----------------------------


def _decode_qr_from_pdf(pdf: bytes) -> str:
    """Render the first PDF page at several DPIs and decode the QR.

    QR detection can be sensitive to resolution, so we try a few DPIs and
    return the first successful decode (empty string if none found).
    """
    import cv2
    import fitz
    import numpy as np

    doc = fitz.open(stream=pdf, filetype="pdf")
    page = doc[0]
    detector = cv2.QRCodeDetector()
    for dpi in (300, 400, 500, 600):
        pix = page.get_pixmap(dpi=dpi)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        data, _, _ = detector.detectAndDecode(img)
        if data:
            return data
    return ""


def test_qr_code_decodes_to_validation_url():
    pytest.importorskip("fitz")
    pytest.importorskip("cv2")

    code = "QRDECODE12345678"
    url = build_validation_url("https://app.example.com", code)
    pdf = CertificateService.generate_certificate_pdf(
        student_name="Aluno QR",
        course_name="Curso QR",
        course_code="QR-1",
        carga_horaria=4,
        certificate_number="CERT-QR-1",
        validation_code=code,
        responsible_admin_name="Admin",
        brand_name="WR",
        validation_url=url,
        issued_date=utc_now(),
        brand_primary_color="#047F37",
    )
    assert _decode_qr_from_pdf(pdf) == url


def test_pdf_is_valid_pdf_bytes():
    pdf = CertificateService.generate_certificate_pdf(
        student_name="A",
        course_name="C",
        course_code="X",
        carga_horaria=1,
        certificate_number="CERT-1",
        validation_code="V1",
        responsible_admin_name="R",
        brand_name="WR",
        validation_url="https://app.example.com/validar-certificado?codigo=V1",
    )
    assert pdf[:4] == b"%PDF"


# -- Phase 4 & 5: demo mode + watermark -----------------------------------


def test_is_demo_certificate_detection():
    real = Certificate(certificate_number="CERT-ABC123", validation_code="V")
    demo = Certificate(certificate_number="DEMO-CERT-ABC", validation_code="V")
    assert is_demo_certificate(real) is False
    assert is_demo_certificate(demo) is True


def test_demo_pdf_contains_demo_marking():
    pdf = CertificateService.generate_certificate_pdf(
        student_name="Aluno Demo",
        course_name="Curso Demo",
        course_code="D-1",
        carga_horaria=2,
        certificate_number="DEMO-CERT-1",
        validation_code="DEMOCODE",
        responsible_admin_name="Admin",
        brand_name="WR",
        validation_url="https://app.example.com/validar-certificado?codigo=DEMOCODE",
        is_demo=True,
    )
    # The PDF text layer carries the demo banner; extract text via PyMuPDF.
    try:
        import fitz
        doc = fitz.open(stream=pdf, filetype="pdf")
        text = doc[0].get_text()
        assert "SEM VALIDADE OFICIAL" in text
        assert "DEMONSTRAÇÃO" in text
    except ImportError:
        # Fallback: raw byte search for the banner string in the content stream.
        assert b"SEM VALIDADE OFICIAL" in pdf


def test_non_demo_pdf_does_not_carry_demo_banner():
    pdf = CertificateService.generate_certificate_pdf(
        student_name="Aluno Real",
        course_name="Curso Real",
        course_code="R-1",
        carga_horaria=2,
        certificate_number="CERT-1",
        validation_code="REALCODE",
        responsible_admin_name="Admin",
        brand_name="WR",
        validation_url="https://app.example.com/validar-certificado?codigo=REALCODE",
        is_demo=False,
    )
    try:
        import fitz
        doc = fitz.open(stream=pdf, filetype="pdf")
        text = doc[0].get_text()
        assert "SEM VALIDADE OFICIAL" not in text
    except ImportError:
        assert b"SEM VALIDADE OFICIAL" not in pdf


# -- Phase 7-13: validation response, journey, privacy, status ------------


@pytest.mark.asyncio
async def test_validate_returns_enriched_journey_and_privacy(client):
    async with AsyncSessionLocal() as db:
        token = current_tenant_id.set(WR_TENANT_ID)
        db.info["tenant_id"] = WR_TENANT_ID
        try:
            admin = User(
                tenant_id=WR_TENANT_ID,
                email=f"qradmin_{uuid.uuid4().hex[:6]}@example.com",
                full_name="Admin QR",
                cpf=make_valid_cpf(),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin)
            await db.flush()
            course, cls, lessons = await _setup_course_with_lessons(db, WR_TENANT_ID, admin.id, n_required=3)
            _user, student = await _setup_student(db, WR_TENANT_ID, name="João QR Silva")
            enrollment = await _complete_enrollment_with_progress(db, WR_TENANT_ID, student, cls, lessons)

            cert = await CertificateService.issue_certificate(
                db,
                tenant_id=WR_TENANT_ID,
                enrollment=enrollment,
                student=student,
                course_id=course.id,
                course_validity_days=course.certificate_validity_days,
                actor_id=admin.id,
            )
            await db.commit()
            code = cert.validation_code
        finally:
            current_tenant_id.reset(token)

    response = await client.post(
        "/api/v1/certificates/validate",
        json={"validation_code": code},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["status"] == "ACTIVE"
    assert body["is_demo"] is False

    # Nested objects
    assert body["certificate"]["number"].startswith("CERT-")
    assert body["certificate"]["validation_code"] == code
    assert body["student"]["name"] == "João QR Silva"
    assert body["course"]["code"].startswith("QR-")
    assert body["course"]["workload_hours"] == 8
    assert body["course"]["modality"] == "EAD"

    # Journey
    journey = body["journey"]
    assert journey["progress"]["required_lessons_total"] == 3
    assert journey["progress"]["required_lessons_completed"] == 3
    assert journey["progress"]["completion_percent"] == 100.0
    step_types = [s["type"] for s in journey["steps"]]
    assert "ENROLLED" in step_types
    assert "COURSE_STARTED" in step_types
    assert "COURSE_COMPLETED" in step_types
    assert "CERTIFICATE_ISSUED" in step_types
    # Per-lesson expandable detail
    assert len(journey["lessons"]) == 3

    # Privacy: no sensitive fields anywhere in the payload
    payload_str = str(body)
    for forbidden in ["cpf", "email", "phone", "address", "user_id", "student_id", "enrollment_id", "actor_id", "payment", "password"]:
        assert forbidden not in payload_str.lower(), f"leaked field: {forbidden}"


@pytest.mark.asyncio
async def test_validate_not_found(client):
    response = await client.post(
        "/api/v1/certificates/validate",
        json={"validation_code": "DOES-NOT-EXIST-12345"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["status"] == "NOT_FOUND"
    assert body["is_demo"] is False


@pytest.mark.asyncio
async def test_validate_expired_status(client):
    async with AsyncSessionLocal() as db:
        token = current_tenant_id.set(WR_TENANT_ID)
        db.info["tenant_id"] = WR_TENANT_ID
        try:
            admin = User(
                tenant_id=WR_TENANT_ID,
                email=f"expadmin_{uuid.uuid4().hex[:6]}@example.com",
                full_name="Admin Exp",
                cpf=make_valid_cpf(),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin)
            await db.flush()
            course, cls, lessons = await _setup_course_with_lessons(
                db, WR_TENANT_ID, admin.id, n_required=2, validity_days=1
            )
            _user, student = await _setup_student(db, WR_TENANT_ID)
            enrollment = await _complete_enrollment_with_progress(db, WR_TENANT_ID, student, cls, lessons)
            cert = await CertificateService.issue_certificate(
                db,
                tenant_id=WR_TENANT_ID,
                enrollment=enrollment,
                student=student,
                course_id=course.id,
                course_validity_days=1,
                actor_id=admin.id,
            )
            # Force expiry in the past
            cert.expires_at = utc_now() - timedelta(days=1)
            await db.commit()
            code = cert.validation_code
        finally:
            current_tenant_id.reset(token)

    body = (await client.post("/api/v1/certificates/validate", json={"validation_code": code})).json()
    assert body["valid"] is False
    assert body["status"] == "EXPIRED"


@pytest.mark.asyncio
async def test_validate_revoked_and_superseded_status(client):
    async with AsyncSessionLocal() as db:
        token = current_tenant_id.set(WR_TENANT_ID)
        db.info["tenant_id"] = WR_TENANT_ID
        try:
            admin = User(
                tenant_id=WR_TENANT_ID,
                email=f"revadmin_{uuid.uuid4().hex[:6]}@example.com",
                full_name="Admin Rev",
                cpf=make_valid_cpf(),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin)
            await db.flush()
            admin_dict = {"user_id": str(admin.id), "role": "admin", "tenant_id": str(WR_TENANT_ID)}
            _course, cls, lessons = await _setup_course_with_lessons(db, WR_TENANT_ID, admin.id, n_required=2)
            _user, student = await _setup_student(db, WR_TENANT_ID)
            enrollment = await _complete_enrollment_with_progress(db, WR_TENANT_ID, student, cls, lessons)

            from app.api.routes.certificates import (
                create_certificate,
                reissue_certificate,
                revoke_certificate,
            )

            first = await create_certificate(
                CertificateCreate(enrollment_id=enrollment.id), db, admin_dict
            )
            await db.commit()
            await db.refresh(first)
            revoked_code = first.validation_code

            await revoke_certificate(
                first.id, CertificateRevokeRequest(reason="Teste revogação"), db, admin_dict
            )
            await db.commit()

            # New enrollment+cert for superseded scenario
            _course2, cls2, lessons2 = await _setup_course_with_lessons(
                db, WR_TENANT_ID, admin.id, n_required=2
            )
            _user2, student2 = await _setup_student(db, WR_TENANT_ID, name="Aluno Supersede")
            enr2 = await _complete_enrollment_with_progress(db, WR_TENANT_ID, student2, cls2, lessons2)
            orig = await create_certificate(
                CertificateCreate(enrollment_id=enr2.id), db, admin_dict
            )
            await db.commit()
            await db.refresh(orig)
            new = await reissue_certificate(
                orig.id, CertificateReissueRequest(reason="Reemissão teste"), db, admin_dict
            )
            await db.commit()
            await db.refresh(new)
            orig_code = orig.validation_code
            new_code = new.validation_code
        finally:
            current_tenant_id.reset(token)

    revoked_body = (await client.post(
        "/api/v1/certificates/validate", json={"validation_code": revoked_code}
    )).json()
    assert revoked_body["status"] == "REVOKED"
    assert revoked_body["valid"] is False
    assert revoked_body["revocation_reason"] == "Teste revogação"

    sup_body = (await client.post(
        "/api/v1/certificates/validate", json={"validation_code": orig_code}
    )).json()
    assert sup_body["status"] == "SUPERSEDED"
    assert sup_body["valid"] is False

    new_body = (await client.post(
        "/api/v1/certificates/validate", json={"validation_code": new_code}
    )).json()
    assert new_body["status"] == "ACTIVE"
    assert new_body["valid"] is True


@pytest.mark.asyncio
async def test_demo_certificate_validates_with_demo_flag(client):
    async with AsyncSessionLocal() as db:
        token = current_tenant_id.set(WR_TENANT_ID)
        db.info["tenant_id"] = WR_TENANT_ID
        try:
            admin = User(
                tenant_id=WR_TENANT_ID,
                email=f"doadmin_{uuid.uuid4().hex[:6]}@example.com",
                full_name="Admin Demo",
                cpf=make_valid_cpf(),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin)
            await db.flush()
            course, cls, lessons = await _setup_course_with_lessons(db, WR_TENANT_ID, admin.id, n_required=2)
            _user, student = await _setup_student(db, WR_TENANT_ID, name="Aluno Demonstração WR")
            enrollment = await _complete_enrollment_with_progress(db, WR_TENANT_ID, student, cls, lessons)
            cert = await CertificateService.issue_certificate(
                db,
                tenant_id=WR_TENANT_ID,
                enrollment=enrollment,
                student=student,
                course_id=course.id,
                course_validity_days=course.certificate_validity_days,
                actor_id=admin.id,
                demo=True,
            )
            await db.commit()
            code = cert.validation_code
            number = cert.certificate_number
        finally:
            current_tenant_id.reset(token)

    body = (await client.post("/api/v1/certificates/validate", json={"validation_code": code})).json()
    assert body["valid"] is True
    assert body["status"] == "ACTIVE"
    assert body["is_demo"] is True
    assert number.startswith("DEMO-")
    assert body["certificate"]["number"].startswith("DEMO-")


# -- Phase 16-17: content hash -------------------------------------------


@pytest.mark.asyncio
async def test_content_hash_is_registry_hash_not_pdf(client):
    async with AsyncSessionLocal() as db:
        token = current_tenant_id.set(WR_TENANT_ID)
        db.info["tenant_id"] = WR_TENANT_ID
        try:
            admin = User(
                tenant_id=WR_TENANT_ID,
                email=f"hashadmin_{uuid.uuid4().hex[:6]}@example.com",
                full_name="Admin Hash",
                cpf=make_valid_cpf(),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin)
            await db.flush()
            course, cls, lessons = await _setup_course_with_lessons(db, WR_TENANT_ID, admin.id, n_required=1)
            _user, student = await _setup_student(db, WR_TENANT_ID)
            enrollment = await _complete_enrollment_with_progress(db, WR_TENANT_ID, student, cls, lessons)
            cert = await CertificateService.issue_certificate(
                db,
                tenant_id=WR_TENANT_ID,
                enrollment=enrollment,
                student=student,
                course_id=course.id,
                course_validity_days=course.certificate_validity_days,
                actor_id=admin.id,
            )
            await db.commit()
            code = cert.validation_code
            stored_hash = cert.content_hash
        finally:
            current_tenant_id.reset(token)

    body = (await client.post("/api/v1/certificates/validate", json={"validation_code": code})).json()
    assert body["certificate"]["content_hash"] == stored_hash
    assert len(stored_hash) == 64  # sha-256 hex


# -- Phase 30: tenant isolation ------------------------------------------


@pytest.mark.asyncio
async def test_tenant_isolation_admin_cannot_access_other_tenant_cert(client):
    from app.models.tenant import Tenant, TenantStatus

    other_tenant_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        # Create a second tenant + admin + cert in it
        other_tenant = Tenant(
            id=other_tenant_id,
            name="Outro Tenant",
            slug=f"outro-{uuid.uuid4().hex[:6]}",
            status=TenantStatus.ACTIVE,
            contact_name="Admin Outro",
            contact_email="admin@outro.example",
        )
        db.add(other_tenant)
        await db.flush()
        admin = User(
            tenant_id=other_tenant_id,
            email=f"otheradmin_{uuid.uuid4().hex[:6]}@example.com",
            full_name="Admin Outro",
            cpf=make_valid_cpf(),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin)
        await db.flush()
        course = Course(
            tenant_id=other_tenant_id,
            code=f"OT-{uuid.uuid4().hex[:5].upper()}",
            name="Curso Outro",
            category="X",
            carga_horaria=4,
            modality=CourseModality.EAD,
            tipo_curso=CourseType.FORMACAO,
            price=10.0,
            certificate_validity_days=365,
        )
        db.add(course)
        await db.flush()
        cls = Class(
            tenant_id=other_tenant_id,
            course_id=course.id,
            responsible_admin_id=admin.id,
            start_date=utc_now().date(),
            end_date=(utc_now() + timedelta(days=30)).date(),
            max_students=10,
            status=ClassStatus.ABERTA,
        )
        db.add(cls)
        await db.flush()
        user = User(
            tenant_id=other_tenant_id,
            email=f"otherstudent_{uuid.uuid4().hex[:6]}@example.com",
            full_name="Aluno Outro",
            cpf=make_valid_cpf(),
            role=UserRole.STUDENT,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        student = Student(tenant_id=other_tenant_id, user_id=user.id, cpf=make_valid_cpf())
        db.add(student)
        await db.flush()
        enrollment = Enrollment(
            tenant_id=other_tenant_id,
            student_id=student.id,
            class_id=cls.id,
            status=EnrollmentStatus.CONCLUIDA,
            price=10.0,
        )
        db.add(enrollment)
        await db.flush()
        token = current_tenant_id.set(other_tenant_id)
        try:
            cert = await CertificateService.issue_certificate(
                db,
                tenant_id=other_tenant_id,
                enrollment=enrollment,
                student=student,
                course_id=course.id,
                course_validity_days=365,
                actor_id=admin.id,
            )
            await db.commit()
            cert_id = cert.id
            code = cert.validation_code
        finally:
            current_tenant_id.reset(token)

    # Public validation by code still works (global, privacy-safe)
    body = (await client.post(
        "/api/v1/certificates/validate", json={"validation_code": code}
    )).json()
    assert body["valid"] is True
    assert body["student"]["name"] == "Aluno Outro"

    # WR admin (default tenant in client) cannot fetch the other tenant's cert
    wr_admin = {
        "user_id": str(uuid.uuid4()),
        "role": "admin",
        "tenant_id": str(WR_TENANT_ID),
    }
    from fastapi import HTTPException

    from app.api.routes.certificates import get_certificate

    async with AsyncSessionLocal() as db:
        token = current_tenant_id.set(WR_TENANT_ID)
        try:
            with pytest.raises(HTTPException) as exc:
                await get_certificate(cert_id, db, wr_admin)
            assert exc.value.status_code == 404
        finally:
            current_tenant_id.reset(token)


# -- Phase 25: PDF download endpoint produces QR PDF ---------------------


@pytest.mark.asyncio
async def test_download_endpoint_generates_pdf_with_qr():
    from starlette.requests import Request

    from app.api.routes.certificates import create_certificate, download_certificate

    async with AsyncSessionLocal() as db:
        token = current_tenant_id.set(WR_TENANT_ID)
        db.info["tenant_id"] = WR_TENANT_ID
        try:
            admin = User(
                tenant_id=WR_TENANT_ID,
                email=f"dladmin_{uuid.uuid4().hex[:6]}@example.com",
                full_name="Admin Download",
                cpf=make_valid_cpf(),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin)
            await db.flush()
            admin_dict = {"user_id": str(admin.id), "role": "admin", "tenant_id": str(WR_TENANT_ID)}
            _course, cls, lessons = await _setup_course_with_lessons(db, WR_TENANT_ID, admin.id, n_required=2)
            user, student = await _setup_student(db, WR_TENANT_ID, name="Aluno Download")
            student_dict = {"user_id": str(user.id), "role": "student", "tenant_id": str(WR_TENANT_ID)}
            enrollment = await _complete_enrollment_with_progress(db, WR_TENANT_ID, student, cls, lessons)
            cert = await create_certificate(
                CertificateCreate(enrollment_id=enrollment.id), db, admin_dict
            )
            await db.commit()
            await db.refresh(cert)
            cert_id = cert.id
            code = cert.validation_code

            request = Request({"type": "http", "method": "GET", "path": "/download", "headers": []})
            response = await download_certificate(cert_id, request, db, student_dict)
            assert response.media_type == "application/pdf"
            assert response.body[:4] == b"%PDF"

            # Verify the QR inside the downloaded PDF decodes to the public URL
            pytest.importorskip("fitz")
            pytest.importorskip("cv2")

            data = _decode_qr_from_pdf(response.body)
            expected = build_validation_url(
                "http://localhost:5173", code
            )
            assert data == expected
            assert "/validar-certificado?codigo=" in data
        finally:
            current_tenant_id.reset(token)
