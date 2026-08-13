"""Testes unitários diretos sobre as funções de rota de aulas.

Executar as funções fora do ASGI permite que o coverage.py trace
o módulo `app.api.routes.lessons` de forma completa.
"""
import uuid
from datetime import timedelta

import pytest

from app.api.routes.lessons import (
    create_lesson,
    create_lesson_material,
    delete_lesson,
    generate_lesson_upload_url,
    get_course_progress,
    get_lesson,
    get_lesson_watch_url,
    list_lesson_materials,
    list_lessons,
    update_lesson,
    update_lesson_progress,
)
from app.core.database import AsyncSessionLocal
from app.core.utils import utc_now
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.lesson import LessonContentType
from app.models.student import Student
from app.schemas.lesson import (
    LessonCreate,
    LessonMaterialCreate,
    LessonProgressCreate,
    LessonUpdate,
)


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


async def _student_user_id(student_id):
    async with AsyncSessionLocal() as db:
        student = await db.get(Student, uuid.UUID(student_id))
        return student.user_id


@pytest.mark.asyncio
async def test_lesson_routes_direct(client, admin_headers, student_user, test_course_data, monkeypatch):
    admin_id = await _admin_id(client, admin_headers)
    course_id = await _create_course(client, admin_headers, test_course_data)
    class_id = await _create_class(client, admin_headers, course_id, admin_id)
    enrollment_id = await _create_enrollment(client, admin_headers, student_user["student_id"], class_id)

    # confirma matrícula para acesso
    async with AsyncSessionLocal() as db:
        enrollment = await db.get(Enrollment, uuid.UUID(enrollment_id))
        enrollment.status = EnrollmentStatus.CONFIRMADA
        await db.commit()

    student_user_id = await _student_user_id(student_user["student_id"])

    async def _mock_upload(*a, **k):
        return "http://upload", "lessons/uuid/video.mp4"

    async def _mock_watch(*a, **k):
        return "http://watch"

    monkeypatch.setattr("app.api.routes.lessons.generate_upload_url", _mock_upload)
    monkeypatch.setattr("app.api.routes.lessons.generate_watch_url", _mock_watch)

    async with AsyncSessionLocal() as db:
        admin_user = {"user_id": str(admin_id), "role": "admin"}
        student_user_dict = {"user_id": str(student_user_id), "role": "student"}

        # create + list
        lesson = await create_lesson(
            course_id,
            LessonCreate(
                course_id=course_id,
                title="Aula 1",
                description="Desc",
                order=1,
                content_type=LessonContentType.UPLOAD,
                duration_seconds=100,
                is_free_preview=False,
            ),
            db,
            admin_user,
        )
        lesson_id = lesson.id

        lessons = await list_lessons(course_id, db, admin_user, 0, 100)
        assert len(lessons) > 0

        # student list
        lessons = await list_lessons(course_id, db, student_user_dict, 0, 100)
        assert len(lessons) > 0

        # get
        got = await get_lesson(course_id, lesson_id, db, admin_user)
        assert got.id == lesson_id

        # update
        updated = await update_lesson(course_id, lesson_id, LessonUpdate(title="Aula 1 atualizada"), db, admin_user)
        assert updated.title == "Aula 1 atualizada"

        # upload url
        upload = await generate_lesson_upload_url(lesson_id, "video.mp4", "video/mp4", 1024, db, admin_user)
        assert "upload_url" in upload

        # watch url
        watch = await get_lesson_watch_url(lesson_id, db, admin_user)
        assert watch["watch_url"] == "http://watch"

        # progress
        progress = await update_lesson_progress(
            lesson_id,
            LessonProgressCreate(watched_seconds=100, completed=True),
            db,
            student_user_dict,
        )
        assert progress.completed is True

        # my progress
        course_progress = await get_course_progress(course_id, db, student_user_dict)
        assert course_progress.percentage == 100.0

        # material
        material = await create_lesson_material(
            lesson_id,
            LessonMaterialCreate(lesson_id=lesson_id, title="Apostila", file_url="http://file"),
            db,
            admin_user,
        )
        assert material.title == "Apostila"

        materials = await list_lesson_materials(lesson_id, db, student_user_dict)
        assert len(materials) == 1

        # youtube watch
        yt_lesson = await create_lesson(
            course_id,
            LessonCreate(
                course_id=course_id,
                title="Aula YT",
                order=2,
                content_type=LessonContentType.YOUTUBE,
                video_url="https://youtube.com/watch?v=123",
            ),
            db,
            admin_user,
        )
        watch_yt = await get_lesson_watch_url(yt_lesson.id, db, admin_user)
        assert watch_yt["watch_url"] == "https://youtube.com/watch?v=123"

        # delete
        await delete_lesson(course_id, lesson_id, db, admin_user)


@pytest.mark.asyncio
async def test_lesson_routes_errors_direct(client, admin_headers, test_course_data):
    admin_id = await _admin_id(client, admin_headers)
    course_id = await _create_course(client, admin_headers, test_course_data)

    async with AsyncSessionLocal() as db:
        admin_user = {"user_id": str(admin_id), "role": "admin"}

        from fastapi import HTTPException

        fake_course = str(uuid.uuid4())
        with pytest.raises(HTTPException) as exc:
            await create_lesson(
                uuid.UUID(fake_course),
                LessonCreate(course_id=uuid.UUID(fake_course), title="Aula"),
                db,
                admin_user,
            )
        assert exc.value.status_code == 404

        fake_lesson = str(uuid.uuid4())
        with pytest.raises(HTTPException) as exc:
            await get_lesson(course_id, uuid.UUID(fake_lesson), db, admin_user)
        assert exc.value.status_code == 404

        with pytest.raises(HTTPException) as exc:
            await generate_lesson_upload_url(uuid.UUID(fake_lesson), "x.mp4", db=db, current_user=admin_user)
        assert exc.value.status_code == 404

        with pytest.raises(HTTPException) as exc:
            await get_lesson_watch_url(uuid.UUID(fake_lesson), db, admin_user)
        assert exc.value.status_code == 404

        with pytest.raises(HTTPException) as exc:
            await create_lesson_material(
                uuid.UUID(fake_lesson),
                LessonMaterialCreate(lesson_id=uuid.UUID(fake_lesson), title="x", file_url="http://"),
                db,
                admin_user,
            )
        assert exc.value.status_code == 404
