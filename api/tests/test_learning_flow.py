import uuid
from datetime import timedelta
from unittest.mock import AsyncMock

from app.core.utils import utc_now


async def _get_admin_id(client, admin_headers):
    me = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert me.status_code == 200
    return me.json()["id"]


async def _full_flow(client, admin_headers, student_user, monkeypatch):
    # 1. admin autentica
    admin_id = await _get_admin_id(client, admin_headers)

    # 2. admin cria curso
    course_code = f"NR-FLOW-{uuid.uuid4().hex[:6].upper()}"
    course_response = await client.post(
        "/api/v1/courses/",
        json={
            "code": course_code,
            "name": "Curso Integrado",
            "category": "Segurança",
            "carga_horaria": 40,
            "modality": "EAD",
            "tipo_curso": "FORMACAO",
            "price": 299.90,
            "description": "Curso para teste de fluxo integrado",
        },
        headers=admin_headers,
    )
    assert course_response.status_code == 201
    course_id = course_response.json()["id"]

    # 3. cria turma
    start = utc_now().date() + timedelta(days=1)
    end = start + timedelta(days=30)
    class_response = await client.post(
        "/api/v1/classes/",
        json={
            "course_id": str(course_id),
            "responsible_admin_id": str(admin_id),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "max_students": 30,
            "location": None,
            "ead_link": "https://ead.wrconsultoria.com.br/test",
            "status": "ABERTA",
            "description": "Turma do fluxo integrado",
        },
        headers=admin_headers,
    )
    assert class_response.status_code == 201
    class_id = class_response.json()["id"]

    # 4. cria aluno
    student_id = student_user["student_id"]

    # 5. cria matrícula
    enrollment_response = await client.post(
        "/api/v1/enrollments/",
        json={
            "student_id": str(student_id),
            "class_id": str(class_id),
            "price": 299.90,
            "status": "PENDENTE",
        },
        headers=admin_headers,
    )
    assert enrollment_response.status_code == 201
    enrollment_id = enrollment_response.json()["id"]

    # 6. confirma a matrícula
    confirm_response = await client.put(
        f"/api/v1/enrollments/{enrollment_id}",
        json={"status": "CONFIRMADA"},
        headers=admin_headers,
    )
    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "CONFIRMADA"

    # 7. cria duas aulas
    lesson1 = await client.post(
        f"/api/v1/lessons/courses/{course_id}/lessons",
        json={
            "title": "Aula 1",
            "description": "Primeira aula",
            "order": 0,
            "content_type": "UPLOAD",
            "duration_seconds": 120,
            "is_free_preview": False,
        },
        headers=admin_headers,
    )
    assert lesson1.status_code == 201
    lesson1_id = lesson1.json()["id"]

    lesson2 = await client.post(
        f"/api/v1/lessons/courses/{course_id}/lessons",
        json={
            "title": "Aula 2",
            "description": "Segunda aula",
            "order": 1,
            "content_type": "UPLOAD",
            "duration_seconds": 100,
            "is_free_preview": False,
        },
        headers=admin_headers,
    )
    assert lesson2.status_code == 201
    lesson2_id = lesson2.json()["id"]

    # 7a. Set storage_key via upload-complete (mocked verify)
    async def _mock_verify(*a, **k):
        return True
    monkeypatch.setattr("app.api.routes.lessons.verify_object_exists", _mock_verify)

    for lid in [lesson1_id, lesson2_id]:
        storage_key = f"tenants/{lesson1.json()['tenant_id']}/courses/{course_id}/lessons/{lid}/video/v.mp4"
        resp = await client.post(
            f"/api/v1/lessons/{lid}/upload-complete",
            params={"storage_key": storage_key},
            headers=admin_headers,
        )
        assert resp.status_code == 200

    # 8. aluno autentica (já autenticado em student_user)
    student_headers = student_user["headers"]

    # 9. aluno acessa as aulas
    lessons_response = await client.get(
        f"/api/v1/lessons/courses/{course_id}/lessons",
        headers=student_headers,
    )
    assert lessons_response.status_code == 200
    lessons = lessons_response.json()
    assert len(lessons) == 2

    # 10. storage mockado retorna watch URL
    expected_watch = "https://mock-s3.example/watch"
    mock_watch = AsyncMock(return_value=expected_watch)
    monkeypatch.setattr("app.api.routes.lessons.generate_watch_url", mock_watch)

    watch1 = await client.get(
        f"/api/v1/lessons/{lesson1_id}/watch-url",
        headers=student_headers,
    )
    assert watch1.status_code == 200
    assert watch1.json()["watch_url"] == expected_watch

    # 11. aluno registra progresso parcial
    progress1 = await client.post(
        f"/api/v1/lessons/{lesson1_id}/progress",
        json={"watched_seconds": 30, "completed": False},
        headers=student_headers,
    )
    assert progress1.status_code == 200
    assert progress1.json()["completed"] is False

    # 12. nenhum certificado é criado
    certs = await client.get("/api/v1/certificates/", headers=admin_headers)
    assert certs.status_code == 200
    assert len(certs.json()) == 0

    # 13. aluno conclui todas as aulas
    progress1_full = await client.post(
        f"/api/v1/lessons/{lesson1_id}/progress",
        json={"watched_seconds": 120, "completed": True},
        headers=student_headers,
    )
    assert progress1_full.status_code == 200
    assert progress1_full.json()["completed"] is True

    progress2 = await client.post(
        f"/api/v1/lessons/{lesson2_id}/progress",
        json={"watched_seconds": 100, "completed": True},
        headers=student_headers,
    )
    assert progress2.status_code == 200
    assert progress2.json()["completed"] is True

    # 14. certificado é criado
    certs = await client.get("/api/v1/certificates/", headers=admin_headers)
    assert certs.status_code == 200
    assert len(certs.json()) == 1
    certificate = certs.json()[0]
    assert certificate["enrollment_id"] == str(enrollment_id)
    assert certificate["certificate_number"].startswith("CERT-")
    assert certificate["validation_code"]

    # 15. repetição da conclusão não cria outro certificado
    progress2_again = await client.post(
        f"/api/v1/lessons/{lesson2_id}/progress",
        json={"watched_seconds": 100, "completed": True},
        headers=student_headers,
    )
    assert progress2_again.status_code == 200

    certs = await client.get("/api/v1/certificates/", headers=admin_headers)
    assert len(certs.json()) == 1

    # 16. código público do certificado é validado
    validation = await client.post(
        "/api/v1/certificates/validate",
        json={"validation_code": certificate["validation_code"]},
    )
    assert validation.status_code == 200
    data = validation.json()
    assert data["valid"] is True
    assert data["certificate_number"] == certificate["certificate_number"]
    assert data["student_name"]
    assert data["course_name"]
    assert data["issued_at"]

    return {
        "course_id": course_id,
        "class_id": class_id,
        "enrollment_id": enrollment_id,
        "certificate": certificate,
    }


async def test_full_learning_certificate_flow(client, admin_headers, student_user, monkeypatch):
    result = await _full_flow(client, admin_headers, student_user, monkeypatch)
    assert result["certificate"]["enrollment_id"] is not None