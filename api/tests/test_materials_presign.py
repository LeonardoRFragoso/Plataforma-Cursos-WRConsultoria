"""Regression tests for lesson materials presign endpoint.

Covers Step 14 — MATERIALS / STORAGE:
- presign endpoint with storage mocked/configured
- invalid file type
- size restriction
- authorized admin
- unauthorized student
- cross-tenant access
- unconfigured storage (S3 mode, no creds → 503)
- configured storage (local mode → 200)

Separates storage configuration failure (503) from application logic failure.
Uses controlled storage abstraction/mocks — no real production bucket needed.
"""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.core.storage import settings as storage_settings


async def _create_course(client, admin_headers):
    code = f"MAT-{uuid.uuid4().hex[:6].upper()}"
    response = await client.post(
        "/api/v1/courses/",
        json={
            "code": code,
            "name": "Curso Materiais Teste",
            "category": "Segurança",
            "carga_horaria": 40,
            "modality": "EAD",
            "tipo_curso": "FORMACAO",
            "price": 199.90,
            "description": "Curso para testes de materiais",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_lesson(client, admin_headers, course_id):
    response = await client.post(
        f"/api/v1/lessons/courses/{course_id}/lessons",
        json={
            "title": "Aula com Materiais",
            "order": 1,
            "content_type": "UPLOAD",
            "is_required": True,
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()


# ─── Authorization ───


async def test_materials_presign_requires_auth(client, admin_headers):
    """Anonymous request → 403 (no credentials)."""
    course_id = await _create_course(client, admin_headers)
    lesson = await _create_lesson(client, admin_headers, course_id)
    response = await client.post(
        f"/api/v1/lessons/{lesson['id']}/materials/presign",
        json={"filename": "doc.pdf", "mime_type": "application/pdf", "size_bytes": 1024},
    )
    assert response.status_code == 403


async def test_materials_presign_student_forbidden(client, admin_headers, student_user):
    """Student cannot presign material uploads → 403 (admin-only)."""
    course_id = await _create_course(client, admin_headers)
    lesson = await _create_lesson(client, admin_headers, course_id)
    response = await client.post(
        f"/api/v1/lessons/{lesson['id']}/materials/presign",
        json={"filename": "doc.pdf", "mime_type": "application/pdf", "size_bytes": 1024},
        headers=student_user["headers"],
    )
    assert response.status_code == 403


async def test_materials_presign_admin_allowed_mocked(client, admin_headers, monkeypatch):
    """Admin can presign material uploads (mocked storage)."""
    course_id = await _create_course(client, admin_headers)
    lesson = await _create_lesson(client, admin_headers, course_id)
    expected_key = f"tenants/{lesson['tenant_id']}/courses/{course_id}/lessons/{lesson['id']}/materials/doc.pdf"
    mock_upload = AsyncMock(return_value=("https://mock-s3.example/upload", expected_key))
    monkeypatch.setattr("app.api.routes.lessons.generate_material_upload_url", mock_upload)

    response = await client.post(
        f"/api/v1/lessons/{lesson['id']}/materials/presign",
        json={"filename": "doc.pdf", "mime_type": "application/pdf", "size_bytes": 1024},
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["upload_url"] == "https://mock-s3.example/upload"
    assert data["storage_key"] == expected_key
    mock_upload.assert_awaited_once()


# ─── Storage configuration ───


async def test_materials_presign_unconfigured_storage_503(client, admin_headers, monkeypatch):
    """S3 mode with no credentials → 503 Storage not configured."""
    course_id = await _create_course(client, admin_headers)
    lesson = await _create_lesson(client, admin_headers, course_id)
    # Force S3 mode with no creds regardless of .env
    monkeypatch.setattr(storage_settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(storage_settings, "STORAGE_ENDPOINT", "")
    monkeypatch.setattr(storage_settings, "STORAGE_ACCESS_KEY", "")
    monkeypatch.setattr(storage_settings, "STORAGE_SECRET_KEY", "")

    response = await client.post(
        f"/api/v1/lessons/{lesson['id']}/materials/presign",
        json={"filename": "doc.pdf", "mime_type": "application/pdf", "size_bytes": 1024},
        headers=admin_headers,
    )
    assert response.status_code == 503
    assert "Storage not configured" in response.json()["detail"]


async def test_materials_presign_local_backend_200(client, admin_headers, monkeypatch):
    """Local storage backend → 200 (returns backend upload URL, not S3)."""
    course_id = await _create_course(client, admin_headers)
    lesson = await _create_lesson(client, admin_headers, course_id)
    monkeypatch.setattr(storage_settings, "STORAGE_BACKEND", "local")

    response = await client.post(
        f"/api/v1/lessons/{lesson['id']}/materials/presign",
        json={"filename": "doc.pdf", "mime_type": "application/pdf", "size_bytes": 1024},
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "upload_url" in data
    assert "storage_key" in data
    # Local mode returns a backend upload endpoint, not an S3 URL
    assert "/api/v1/storage/upload" in data["upload_url"]


# ─── Validation ───


async def test_materials_presign_invalid_mime_type(client, admin_headers, monkeypatch):
    """Invalid MIME type → 415 Unsupported Media Type."""
    course_id = await _create_course(client, admin_headers)
    lesson = await _create_lesson(client, admin_headers, course_id)
    # Configure S3 creds so we reach the MIME validation
    monkeypatch.setattr(storage_settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(storage_settings, "STORAGE_ENDPOINT", "http://storage:9000")
    monkeypatch.setattr(storage_settings, "STORAGE_ACCESS_KEY", "test-key")
    monkeypatch.setattr(storage_settings, "STORAGE_SECRET_KEY", "test-secret")
    monkeypatch.setattr(storage_settings, "STORAGE_BUCKET", "wr-materials")

    response = await client.post(
        f"/api/v1/lessons/{lesson['id']}/materials/presign",
        json={"filename": "malware.exe", "mime_type": "application/x-msdownload", "size_bytes": 1024},
        headers=admin_headers,
    )
    assert response.status_code == 415


async def test_materials_presign_exceeds_max_size(client, admin_headers, monkeypatch):
    """File exceeding MAX_MATERIAL_SIZE → 413 Request Entity Too Large."""
    course_id = await _create_course(client, admin_headers)
    lesson = await _create_lesson(client, admin_headers, course_id)
    monkeypatch.setattr(storage_settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(storage_settings, "STORAGE_ENDPOINT", "http://storage:9000")
    monkeypatch.setattr(storage_settings, "STORAGE_ACCESS_KEY", "test-key")
    monkeypatch.setattr(storage_settings, "STORAGE_SECRET_KEY", "test-secret")
    monkeypatch.setattr(storage_settings, "STORAGE_BUCKET", "wr-materials")

    from app.core.storage import MAX_MATERIAL_SIZE
    response = await client.post(
        f"/api/v1/lessons/{lesson['id']}/materials/presign",
        json={
            "filename": "huge.pdf",
            "mime_type": "application/pdf",
            "size_bytes": MAX_MATERIAL_SIZE + 1,
        },
        headers=admin_headers,
    )
    assert response.status_code == 413


# ─── Lesson resolution ───


async def test_materials_presign_lesson_not_found(client, admin_headers):
    """Nonexistent lesson → 404."""
    fake_lesson_id = uuid.uuid4()
    response = await client.post(
        f"/api/v1/lessons/{fake_lesson_id}/materials/presign",
        json={"filename": "doc.pdf", "mime_type": "application/pdf", "size_bytes": 1024},
        headers=admin_headers,
    )
    assert response.status_code == 404


# ─── Cross-tenant isolation ───


async def test_materials_presign_cross_tenant_denied(client, admin_headers, monkeypatch):
    """Admin from WR cannot presign materials for an Alfa lesson → 404 (tenant-scoped)."""
    from app.core.constants import WR_TENANT_ID
    from app.core.database import AsyncSessionLocal
    from app.core.security import create_access_token, hash_password
    from app.models.course import Course, CourseModality, CourseType
    from app.models.lesson import Lesson, LessonContentType
    from app.models.tenant import Tenant, TenantStatus
    from app.models.user import User, UserRole
    from sqlalchemy import text

    # Seed Alfa tenant
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await db.execute(text(f"SET LOCAL app.current_tenant = '{WR_TENANT_ID}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        alfa = Tenant(
            name="Alfa Academy",
            slug="alfa",
            status=TenantStatus.ACTIVE,
            contact_name="Alfa Admin",
            contact_email="admin@alfa.test",
            primary_color="#E86A17",
        )
        db.add(alfa)
        await db.commit()
        await db.refresh(alfa)
        alfa_id = alfa.id

        # Create course + lesson in Alfa
        course = Course(
            tenant_id=alfa_id,
            code="ALFA-MAT-01",
            name="Alfa Materials Course",
            category="Test",
            carga_horaria=8,
            modality=CourseModality.EAD,
            tipo_curso=CourseType.FORMACAO,
            price=99.90,
        )
        db.add(course)
        await db.commit()
        await db.refresh(course)

        lesson = Lesson(
            tenant_id=alfa_id,
            course_id=course.id,
            title="Alfa Lesson",
            order=1,
            content_type=LessonContentType.UPLOAD,
            is_required=True,
        )
        db.add(lesson)
        await db.commit()
        await db.refresh(lesson)
        alfa_lesson_id = lesson.id

        # Create Alfa admin
        alfa_admin = User(
            email="alfamat@alfa.test",
            full_name="Alfa Mat Admin",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=alfa_id,
        )
        db.add(alfa_admin)
        await db.commit()
        await db.refresh(alfa_admin)
        alfa_admin_id = alfa_admin.id

    # Alfa admin token
    alfa_token = create_access_token(
        {"sub": str(alfa_admin_id), "role": "admin", "tenant_id": str(alfa_id)}
    )

    # WR admin tries to presign for Alfa lesson → 404 (lesson not found in WR)
    response = await client.post(
        f"/api/v1/lessons/{alfa_lesson_id}/materials/presign",
        json={"filename": "doc.pdf", "mime_type": "application/pdf", "size_bytes": 1024},
        headers={"Authorization": f"Bearer {admin_headers['Authorization'].split(' ')[1]}", "x-tenant-slug": "wr"},
    )
    assert response.status_code == 404

    # Alfa admin CAN presign for their own lesson
    mock_upload = AsyncMock(return_value=("https://mock-s3.example/upload", "key"))
    monkeypatch.setattr("app.api.routes.lessons.generate_material_upload_url", mock_upload)
    response = await client.post(
        f"/api/v1/lessons/{alfa_lesson_id}/materials/presign",
        json={"filename": "doc.pdf", "mime_type": "application/pdf", "size_bytes": 1024},
        headers={"Authorization": f"Bearer {alfa_token}", "x-tenant-slug": "alfa"},
    )
    assert response.status_code == 200
