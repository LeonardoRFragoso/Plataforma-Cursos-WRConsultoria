import uuid
from datetime import timedelta
from unittest.mock import AsyncMock

from app.core.storage import settings as storage_settings
from app.core.utils import utc_now


async def _create_course(client, admin_headers):
    code = f"NR-LSN-{uuid.uuid4().hex[:6].upper()}"
    response = await client.post(
        "/api/v1/courses/",
        json={
            "code": code,
            "name": "Curso de Teste - Aulas",
            "category": "Segurança",
            "carga_horaria": 40,
            "modality": "EAD",
            "tipo_curso": "FORMACAO",
            "price": 299.90,
            "description": "Curso para testes de aulas",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _get_admin_id(client, admin_headers):
    me = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert me.status_code == 200
    return me.json()["id"]


async def _create_class(client, admin_headers, course_id, responsible_admin_id, status="ABERTA"):
    start = utc_now().date() + timedelta(days=1)
    end = start + timedelta(days=30)
    response = await client.post(
        "/api/v1/classes/",
        json={
            "course_id": str(course_id),
            "responsible_admin_id": str(responsible_admin_id),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "max_students": 30,
            "location": "Sala de Testes",
            "ead_link": "https://ead.wrconsultoria.com.br/test",
            "status": status,
            "description": "Turma de teste",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_student(client, admin_headers, class_id=None):
    if class_id is None:
        course_id = await _create_course(client, admin_headers)
        responsible_admin_id = await _get_admin_id(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, responsible_admin_id)
    email = f"student_lsn_{uuid.uuid4().hex[:8]}@example.com"
    cpf = f"{uuid.uuid4().int % 10**11:011d}"
    response = await client.post(
        "/api/v1/students/",
        json={
            "email": email,
            "full_name": "Aluno Aulas",
            "password": "student123",
            "cpf": cpf,
            "phone": "(11) 99999-9999",
            "company": "Empresa Teste",
            "address": "Rua do Aluno, 123",
            "city": "São Paulo",
            "state": "SP",
            "zip_code": "01000-000",
            "class_id": class_id,
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_enrollment(client, admin_headers, student_id, class_id, status="CONFIRMADA"):
    response = await client.post(
        "/api/v1/enrollments/",
        json={
            "student_id": str(student_id),
            "class_id": str(class_id),
            "price": 299.90,
            "status": status,
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_lesson(client, admin_headers, course_id, extra=None):
    payload = {
        "title": f"Aula {uuid.uuid4().hex[:6]}",
        "description": "Descrição da aula",
        "order": 1,
        "content_type": "UPLOAD",
        "duration_seconds": 120,
        "is_free_preview": False,
    }
    if extra:
        payload.update(extra)
    response = await client.post(
        f"/api/v1/lessons/courses/{course_id}/lessons",
        json=payload,
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()


# Rotas administrativas


async def test_create_lesson_as_admin(client, admin_headers):
    course_id = await _create_course(client, admin_headers)
    lesson = await _create_lesson(client, admin_headers, course_id)
    assert lesson["course_id"] == str(course_id)
    assert lesson["title"]


async def test_create_lesson_as_student_forbidden(client, admin_headers, student_user):
    course_id = await _create_course(client, admin_headers)
    response = await client.post(
        f"/api/v1/lessons/courses/{course_id}/lessons",
        json={
            "title": "Aula",
            "order": 1,
            "content_type": "UPLOAD",
            "duration_seconds": 120,
            "is_free_preview": False,
        },
        headers=student_user["headers"],
    )
    assert response.status_code == 403


async def test_create_lesson_course_not_found(client, admin_headers):
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.post(
        f"/api/v1/lessons/courses/{fake_id}/lessons",
        json={
            "title": "Aula",
            "order": 1,
            "content_type": "UPLOAD",
            "duration_seconds": 120,
            "is_free_preview": False,
        },
        headers=admin_headers,
    )
    assert response.status_code == 404


async def test_create_lesson_invalid_payload(client, admin_headers):
    course_id = await _create_course(client, admin_headers)
    response = await client.post(
        f"/api/v1/lessons/courses/{course_id}/lessons",
        json={
            "title": "",
            "order": -1,
            "content_type": "INVALID",
        },
        headers=admin_headers,
    )
    assert response.status_code == 422


async def test_update_lesson(client, admin_headers):
    course_id = await _create_course(client, admin_headers)
    lesson = await _create_lesson(client, admin_headers, course_id, {"title": "Original"})
    lesson_id = lesson["id"]

    response = await client.put(
        f"/api/v1/lessons/courses/{course_id}/lessons/{lesson_id}",
        json={"title": "Atualizado", "order": 2},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Atualizado"
    assert response.json()["order"] == 2


async def test_delete_lesson(client, admin_headers):
    course_id = await _create_course(client, admin_headers)
    lesson = await _create_lesson(client, admin_headers, course_id)
    lesson_id = lesson["id"]

    response = await client.delete(
        f"/api/v1/lessons/courses/{course_id}/lessons/{lesson_id}",
        headers=admin_headers,
    )
    assert response.status_code == 204

    response = await client.get(
        f"/api/v1/lessons/courses/{course_id}/lessons/{lesson_id}",
        headers=admin_headers,
    )
    assert response.status_code == 404


async def test_list_lessons_admin(client, admin_headers):
    course_id = await _create_course(client, admin_headers)
    await _create_lesson(client, admin_headers, course_id, {"order": 0})
    await _create_lesson(client, admin_headers, course_id, {"order": 2})
    await _create_lesson(client, admin_headers, course_id, {"order": 1})

    response = await client.get(
        f"/api/v1/lessons/courses/{course_id}/lessons",
        headers=admin_headers,
    )
    assert response.status_code == 200
    lessons = response.json()
    assert len(lessons) == 3
    orders = [lesson["order"] for lesson in lessons]
    assert orders == sorted(orders)


async def test_create_lesson_anonymous_forbidden(client, admin_headers):
    course_id = await _create_course(client, admin_headers)
    response = await client.post(
        f"/api/v1/lessons/courses/{course_id}/lessons",
        json={
            "title": "Aula",
            "order": 1,
            "content_type": "UPLOAD",
        },
    )
    assert response.status_code in (401, 403)


# Materiais e armazenamento


async def test_generate_upload_url_mocked(client, admin_headers, monkeypatch):
    course_id = await _create_course(client, admin_headers)
    lesson = await _create_lesson(client, admin_headers, course_id)
    lesson_id = lesson["id"]

    expected_key = f"tenants/{lesson['tenant_id']}/courses/{course_id}/lessons/{lesson_id}/video/video.mp4"
    mock_upload = AsyncMock(return_value=("https://mock-s3.example/upload", expected_key))
    monkeypatch.setattr("app.api.routes.lessons.generate_upload_url", mock_upload)

    response = await client.post(
        f"/api/v1/lessons/{lesson_id}/upload-presign",
        json={"filename": "video.mp4", "mime_type": "video/mp4", "size_bytes": 1048576},
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["upload_url"] == "https://mock-s3.example/upload"
    assert data["storage_key"] == expected_key
    mock_upload.assert_awaited_once()


async def test_generate_upload_url_no_storage(client, admin_headers, monkeypatch):
    course_id = await _create_course(client, admin_headers)
    lesson = await _create_lesson(client, admin_headers, course_id)
    lesson_id = lesson["id"]

    monkeypatch.undo()
    response = await client.post(
        f"/api/v1/lessons/{lesson_id}/upload-presign",
        json={"filename": "video.mp4", "mime_type": "video/mp4", "size_bytes": 1048576},
        headers=admin_headers,
    )
    assert response.status_code == 503


async def test_generate_upload_url_invalid_mime(client, admin_headers, monkeypatch):
    course_id = await _create_course(client, admin_headers)
    lesson = await _create_lesson(client, admin_headers, course_id)
    lesson_id = lesson["id"]

    monkeypatch.setattr(storage_settings, "STORAGE_ENDPOINT", "http://storage:9000")
    monkeypatch.setattr(storage_settings, "STORAGE_ACCESS_KEY", "test-key")
    monkeypatch.setattr(storage_settings, "STORAGE_SECRET_KEY", "test-secret")
    monkeypatch.setattr(storage_settings, "STORAGE_BUCKET", "wr-videos")

    response = await client.post(
        f"/api/v1/lessons/{lesson_id}/upload-presign",
        json={"filename": "image.png", "mime_type": "image/png", "size_bytes": 1048576},
        headers=admin_headers,
    )
    assert response.status_code == 415


async def test_generate_upload_url_max_size(client, admin_headers, monkeypatch):
    course_id = await _create_course(client, admin_headers)
    lesson = await _create_lesson(client, admin_headers, course_id)
    lesson_id = lesson["id"]

    monkeypatch.setattr(storage_settings, "STORAGE_ENDPOINT", "http://storage:9000")
    monkeypatch.setattr(storage_settings, "STORAGE_ACCESS_KEY", "test-key")
    monkeypatch.setattr(storage_settings, "STORAGE_SECRET_KEY", "test-secret")
    monkeypatch.setattr(storage_settings, "STORAGE_BUCKET", "wr-videos")

    from app.core.storage import MAX_UPLOAD_SIZE
    response = await client.post(
        f"/api/v1/lessons/{lesson_id}/upload-presign",
        json={"filename": "video.mp4", "mime_type": "video/mp4", "size_bytes": MAX_UPLOAD_SIZE + 1},
        headers=admin_headers,
    )
    assert response.status_code == 413


async def test_generate_watch_url_mocked(client, admin_headers, student_user, monkeypatch):
    course_id = await _create_course(client, admin_headers)
    admin_id = await _get_admin_id(client, admin_headers)
    class_id = await _create_class(client, admin_headers, course_id, admin_id)
    student_id = student_user["student_id"]
    await _create_enrollment(client, admin_headers, student_id, class_id)
    # storage_key is backend-owned; we need to set it via DB or mock the upload-complete
    lesson = await _create_lesson(client, admin_headers, course_id, {"content_type": "UPLOAD"})
    lesson_id = lesson["id"]

    # Mock verify_object_exists so upload-complete succeeds
    mock_verify = AsyncMock(return_value=True)
    monkeypatch.setattr("app.api.routes.lessons.verify_object_exists", mock_verify)

    # Use upload-complete to set storage_key
    storage_key = f"tenants/{lesson['tenant_id']}/courses/{course_id}/lessons/{lesson_id}/video/video.mp4"
    response = await client.post(
        f"/api/v1/lessons/{lesson_id}/upload-complete",
        params={"storage_key": storage_key},
        headers=admin_headers,
    )
    assert response.status_code == 200

    mock_watch = AsyncMock(return_value="https://mock-s3.example/watch")
    monkeypatch.setattr("app.api.routes.lessons.generate_watch_url", mock_watch)

    response = await client.get(
        f"/api/v1/lessons/{lesson_id}/watch-url",
        headers=student_user["headers"],
    )
    assert response.status_code == 200
    assert response.json()["watch_url"] == "https://mock-s3.example/watch"
    mock_watch.assert_awaited_once()


async def test_watch_url_no_enrollment_forbidden(client, admin_headers, student_user):
    course_id = await _create_course(client, admin_headers)
    lesson = await _create_lesson(client, admin_headers, course_id, {"content_type": "UPLOAD"})
    lesson_id = lesson["id"]
    response = await client.get(
        f"/api/v1/lessons/{lesson_id}/watch-url",
        headers=student_user["headers"],
    )
    assert response.status_code == 403


async def test_watch_url_free_preview_no_enrollment(client, admin_headers, student_user):
    course_id = await _create_course(client, admin_headers)
    lesson = await _create_lesson(
        client, admin_headers, course_id,
        {"content_type": "YOUTUBE", "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
    )
    lesson_id = lesson["id"]
    response = await client.get(
        f"/api/v1/lessons/{lesson_id}/watch-url",
        headers=student_user["headers"],
    )
    assert response.status_code == 200
    assert "youtube.com" in response.json()["watch_url"]


async def test_watch_url_pending_enrollment_forbidden(client, admin_headers, student_user):
    course_id = await _create_course(client, admin_headers)
    admin_id = await _get_admin_id(client, admin_headers)
    class_id = await _create_class(client, admin_headers, course_id, admin_id)
    student_id = student_user["student_id"]
    await _create_enrollment(client, admin_headers, student_id, class_id, status="PENDENTE")
    lesson = await _create_lesson(client, admin_headers, course_id, {"content_type": "UPLOAD"})
    lesson_id = lesson["id"]
    response = await client.get(
        f"/api/v1/lessons/{lesson_id}/watch-url",
        headers=student_user["headers"],
    )
    assert response.status_code == 403


# Progresso


async def test_progress_initial(client, admin_headers, student_user):
    course_id = await _create_course(client, admin_headers)
    admin_id = await _get_admin_id(client, admin_headers)
    class_id = await _create_class(client, admin_headers, course_id, admin_id)
    student_id = student_user["student_id"]
    await _create_enrollment(client, admin_headers, student_id, class_id)
    lesson = await _create_lesson(client, admin_headers, course_id, {"duration_seconds": 120})
    lesson_id = lesson["id"]

    response = await client.post(
        f"/api/v1/lessons/{lesson_id}/progress",
        json={"watched_seconds": 30, "completed": False},
        headers=student_user["headers"],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["watched_seconds"] == 30
    assert data["completed"] is False


async def test_progress_negative_seconds(client, admin_headers, student_user):
    course_id = await _create_course(client, admin_headers)
    admin_id = await _get_admin_id(client, admin_headers)
    class_id = await _create_class(client, admin_headers, course_id, admin_id)
    student_id = student_user["student_id"]
    await _create_enrollment(client, admin_headers, student_id, class_id)
    lesson = await _create_lesson(client, admin_headers, course_id, {"duration_seconds": 120})
    lesson_id = lesson["id"]

    response = await client.post(
        f"/api/v1/lessons/{lesson_id}/progress",
        json={"watched_seconds": -1, "completed": False},
        headers=student_user["headers"],
    )
    assert response.status_code == 422


async def test_progress_over_duration(client, admin_headers, student_user):
    course_id = await _create_course(client, admin_headers)
    admin_id = await _get_admin_id(client, admin_headers)
    class_id = await _create_class(client, admin_headers, course_id, admin_id)
    student_id = student_user["student_id"]
    await _create_enrollment(client, admin_headers, student_id, class_id)
    lesson = await _create_lesson(client, admin_headers, course_id, {"duration_seconds": 120})
    lesson_id = lesson["id"]
    response = await client.post(
        f"/api/v1/lessons/{lesson_id}/progress",
        json={"watched_seconds": 121, "completed": False},
        headers=student_user["headers"],
    )
    assert response.status_code == 422


async def test_progress_completion_does_not_revert(client, admin_headers, student_user):
    course_id = await _create_course(client, admin_headers)
    admin_id = await _get_admin_id(client, admin_headers)
    class_id = await _create_class(client, admin_headers, course_id, admin_id)
    student_id = student_user["student_id"]
    await _create_enrollment(client, admin_headers, student_id, class_id)
    lesson = await _create_lesson(client, admin_headers, course_id, {"duration_seconds": 120})
    lesson_id = lesson["id"]

    response = await client.post(
        f"/api/v1/lessons/{lesson_id}/progress",
        json={"watched_seconds": 120, "completed": True},
        headers=student_user["headers"],
    )
    assert response.status_code == 200
    assert response.json()["completed"] is True

    response = await client.post(
        f"/api/v1/lessons/{lesson_id}/progress",
        json={"watched_seconds": 10, "completed": False},
        headers=student_user["headers"],
    )
    assert response.status_code == 200
    assert response.json()["completed"] is True
    assert response.json()["watched_seconds"] == 120


async def test_progress_other_course_forbidden(client, admin_headers, student_user):
    other_course = await _create_course(client, admin_headers)
    lesson = await _create_lesson(client, admin_headers, other_course)
    response = await client.post(
        f"/api/v1/lessons/{lesson['id']}/progress",
        json={"watched_seconds": 10, "completed": False},
        headers=student_user["headers"],
    )
    assert response.status_code == 403


async def test_progress_course_complete_triggers_certificate(client, admin_headers, student_user):
    course_id = await _create_course(client, admin_headers)
    admin_id = await _get_admin_id(client, admin_headers)
    class_id = await _create_class(client, admin_headers, course_id, admin_id)
    student_id = student_user["student_id"]
    await _create_enrollment(client, admin_headers, student_id, class_id)
    lesson1 = await _create_lesson(client, admin_headers, course_id, {"duration_seconds": 120, "order": 0})
    lesson2 = await _create_lesson(client, admin_headers, course_id, {"duration_seconds": 100, "order": 1})

    response = await client.post(
        f"/api/v1/lessons/{lesson1['id']}/progress",
        json={"watched_seconds": 120, "completed": True},
        headers=student_user["headers"],
    )
    assert response.status_code == 200

    certificates = await client.get("/api/v1/certificates/", headers=admin_headers)
    assert certificates.status_code == 200
    assert len(certificates.json()) == 0

    response = await client.post(
        f"/api/v1/lessons/{lesson2['id']}/progress",
        json={"watched_seconds": 100, "completed": True},
        headers=student_user["headers"],
    )
    assert response.status_code == 200

    certificates = await client.get("/api/v1/certificates/", headers=admin_headers)
    assert certificates.status_code == 200
    assert len(certificates.json()) == 1

    # repetição idempotente
    response = await client.post(
        f"/api/v1/lessons/{lesson2['id']}/progress",
        json={"watched_seconds": 100, "completed": True},
        headers=student_user["headers"],
    )
    assert response.status_code == 200

    certificates = await client.get("/api/v1/certificates/", headers=admin_headers)
    assert len(certificates.json()) == 1