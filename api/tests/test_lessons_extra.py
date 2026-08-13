from datetime import timedelta

from app.core.utils import utc_now


def _class_payload(course_id, admin_id):
    today = utc_now().date()
    return {
        "course_id": str(course_id),
        "responsible_admin_id": str(admin_id),
        "start_date": today.isoformat(),
        "end_date": (today + timedelta(days=30)).isoformat(),
        "max_students": 20,
    }


async def _admin_id(client, admin_headers):
    me = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert me.status_code == 200
    return me.json()["id"]


async def _create_course(client, admin_headers, payload):
    response = await client.post("/api/v1/courses/", json=payload, headers=admin_headers)
    assert response.status_code == 201
    return response.json()["id"]


async def _create_class(client, admin_headers, course_id, admin_id):
    payload = _class_payload(course_id, admin_id)
    response = await client.post("/api/v1/classes/", json=payload, headers=admin_headers)
    assert response.status_code == 201
    return response.json()["id"]


async def _create_enrollment(client, admin_headers, student_id, class_id):
    payload = {
        "student_id": str(student_id),
        "class_id": str(class_id),
        "price": 100.0,
    }
    response = await client.post("/api/v1/enrollments/", json=payload, headers=admin_headers)
    assert response.status_code == 201
    return response.json()["id"]


async def _create_lesson(client, admin_headers, course_id, **extra):
    payload = {
        "course_id": str(course_id),
        "title": "Aula de teste",
        "description": "Descrição",
        "order": 1,
        "content_type": "UPLOAD",
        "duration_seconds": 100,
    }
    payload.update(extra)
    response = await client.post(
        f"/api/v1/lessons/courses/{course_id}/lessons",
        json=payload,
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


class TestLessonExtra:
    async def test_upload_and_watch_url(self, client, admin_headers, test_course_data, monkeypatch):
        async def _mock_upload(*a, **k):
            return "http://upload", "lessons/uuid/aula.mp4"

        async def _mock_watch(*a, **k):
            return "http://watch"

        monkeypatch.setattr("app.api.routes.lessons.generate_upload_url", _mock_upload)
        monkeypatch.setattr("app.api.routes.lessons.generate_watch_url", _mock_watch)

        course_id = await _create_course(client, admin_headers, test_course_data)
        lesson_id = await _create_lesson(client, admin_headers, course_id)

        response = await client.post(
            f"/api/v1/lessons/{lesson_id}/upload-url",
            params={"filename": "aula.mp4", "content_type": "video/mp4", "content_length": 1024},
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert "upload_url" in response.json()

        response = await client.get(
            f"/api/v1/lessons/{lesson_id}/watch-url",
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["watch_url"] == "http://watch"

    async def test_watch_youtube(self, client, admin_headers, test_course_data):
        course_id = await _create_course(client, admin_headers, test_course_data)
        lesson_id = await _create_lesson(
            client,
            admin_headers,
            course_id,
            content_type="YOUTUBE",
            video_url="https://youtube.com/watch?v=123",
        )

        response = await client.get(
            f"/api/v1/lessons/{lesson_id}/watch-url",
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["watch_url"] == "https://youtube.com/watch?v=123"

    async def test_progress_and_certificate(self, client, admin_headers, student_user, test_course_data):
        admin_id = await _admin_id(client, admin_headers)
        course_id = await _create_course(client, admin_headers, test_course_data)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        enrollment_id = await _create_enrollment(client, admin_headers, student_user["student_id"], class_id)

        await client.put(
            f"/api/v1/enrollments/{enrollment_id}",
            json={"status": "CONFIRMADA"},
            headers=admin_headers,
        )

        lesson_id = await _create_lesson(
            client,
            admin_headers,
            course_id,
            duration_seconds=100,
            is_free_preview=False,
        )

        response = await client.post(
            f"/api/v1/lessons/{lesson_id}/progress",
            json={"watched_seconds": 100, "completed": True},
            headers=student_user["headers"],
        )
        assert response.status_code == 200
        assert response.json()["completed"] is True

        response = await client.get(
            f"/api/v1/lessons/courses/{course_id}/my-progress",
            headers=student_user["headers"],
        )
        assert response.status_code == 200
        assert response.json()["percentage"] == 100.0

        certs = await client.get("/api/v1/certificates/", headers=admin_headers)
        assert certs.status_code == 200
        assert len(certs.json()) == 1

    async def test_progress_not_negative(self, client, admin_headers, student_user, test_course_data):
        admin_id = await _admin_id(client, admin_headers)
        course_id = await _create_course(client, admin_headers, test_course_data)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        enrollment_id = await _create_enrollment(client, admin_headers, student_user["student_id"], class_id)
        await client.put(
            f"/api/v1/enrollments/{enrollment_id}",
            json={"status": "CONFIRMADA"},
            headers=admin_headers,
        )
        lesson_id = await _create_lesson(client, admin_headers, course_id, duration_seconds=100)

        response = await client.post(
            f"/api/v1/lessons/{lesson_id}/progress",
            json={"watched_seconds": -1, "completed": False},
            headers=student_user["headers"],
        )
        assert response.status_code == 422

    async def test_lesson_materials(self, client, admin_headers, student_user, test_course_data):
        admin_id = await _admin_id(client, admin_headers)
        course_id = await _create_course(client, admin_headers, test_course_data)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        enrollment_id = await _create_enrollment(client, admin_headers, student_user["student_id"], class_id)
        await client.put(
            f"/api/v1/enrollments/{enrollment_id}",
            json={"status": "CONFIRMADA"},
            headers=admin_headers,
        )
        lesson_id = await _create_lesson(client, admin_headers, course_id)

        response = await client.post(
            f"/api/v1/lessons/{lesson_id}/materials",
            json={"lesson_id": str(lesson_id), "title": "Apostila", "file_url": "http://file.pdf"},
            headers=admin_headers,
        )
        assert response.status_code == 201

        response = await client.get(
            f"/api/v1/lessons/{lesson_id}/materials",
            headers=student_user["headers"],
        )
        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_lessons_student_journey(self, client, admin_headers, student_user, test_course_data):
        admin_id = await _admin_id(client, admin_headers)
        course_id = await _create_course(client, admin_headers, test_course_data)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        enrollment_id = await _create_enrollment(client, admin_headers, student_user["student_id"], class_id)
        await client.put(
            f"/api/v1/enrollments/{enrollment_id}",
            json={"status": "CONFIRMADA"},
            headers=admin_headers,
        )

        # aula paga
        lesson_id = await _create_lesson(
            client,
            admin_headers,
            course_id,
            content_type="UPLOAD",
            storage_key="lessons/uuid/video.mp4",
            duration_seconds=100,
            is_free_preview=False,
        )

        response = await client.get(
            f"/api/v1/lessons/courses/{course_id}/lessons",
            headers=student_user["headers"],
        )
        assert response.status_code == 200
        assert len(response.json()) > 0

        response = await client.get(
            f"/api/v1/lessons/courses/{course_id}/lessons/{lesson_id}",
            headers=student_user["headers"],
        )
        assert response.status_code == 200

        response = await client.get(
            f"/api/v1/lessons/courses/{course_id}/my-progress",
            headers=student_user["headers"],
        )
        assert response.status_code == 200

    async def test_lessons_forbidden_without_enrollment(self, client, admin_headers, student_user, test_course_data):
        course_id = await _create_course(client, admin_headers, test_course_data)
        lesson_id = await _create_lesson(
            client,
            admin_headers,
            course_id,
            content_type="UPLOAD",
            storage_key="lessons/uuid/video.mp4",
            is_free_preview=False,
        )

        # listar sem matrícula ainda retorna 200, mas esconde URLs
        response = await client.get(
            f"/api/v1/lessons/courses/{course_id}/lessons",
            headers=student_user["headers"],
        )
        assert response.status_code == 200

        response = await client.get(
            f"/api/v1/lessons/{lesson_id}/watch-url",
            headers=student_user["headers"],
        )
        assert response.status_code == 403
