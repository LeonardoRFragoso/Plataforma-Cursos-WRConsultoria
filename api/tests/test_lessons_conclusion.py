"""Testes de hardening do fluxo de conclusão de aulas e certificados."""
import uuid
from datetime import timedelta

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.core.utils import utc_now
from app.models.certificate import Certificate
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.lesson import LessonProgress


async def _get_admin_id(client, admin_headers):
    me = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert me.status_code == 200
    return me.json()["id"]


async def _create_course(client, admin_headers):
    code = f"NR-CONC-{uuid.uuid4().hex[:6].upper()}"
    response = await client.post(
        "/api/v1/courses/",
        json={
            "code": code,
            "name": "Curso de Conclusão",
            "category": "Segurança",
            "carga_horaria": 40,
            "modality": "PRESENCIAL",
            "tipo_curso": "FORMACAO",
            "price": 299.90,
            "description": "Curso para testes de conclusão",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_class(client, admin_headers, course_id, responsible_admin_id, status="ABERTA", start_offset_days=1):
    start = utc_now().date() + timedelta(days=start_offset_days)
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
            "ead_link": None,
            "status": status,
            "description": "Turma de conclusão",
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




async def _complete_lesson(client, lesson_id, student_headers, seconds=120):
    response = await client.post(
        f"/api/v1/lessons/{lesson_id}/progress",
        json={"watched_seconds": seconds, "completed": True},
        headers=student_headers,
    )
    return response


async def _enrollment_status_db(enrollment_id: str):
    async with AsyncSessionLocal() as db:
        enrollment = await db.get(Enrollment, uuid.UUID(enrollment_id))
        return enrollment.status if enrollment else None


async def _certificate_count_db(enrollment_id: str | None = None):
    async with AsyncSessionLocal() as db:
        stmt = select(func.count(Certificate.id))
        if enrollment_id:
            stmt = stmt.where(Certificate.enrollment_id == uuid.UUID(enrollment_id))
        result = await db.execute(stmt)
        return result.scalar() or 0


async def _lesson_progress_count(lesson_id: str, student_id: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(func.count(LessonProgress.id)).where(
                LessonProgress.lesson_id == uuid.UUID(lesson_id),
                LessonProgress.student_id == uuid.UUID(student_id),
            )
        )
        return result.scalar() or 0


async def test_last_lesson_completes_correct_enrollment(client, admin_headers, student_user):
    course_id = await _create_course(client, admin_headers)
    admin_id = await _get_admin_id(client, admin_headers)
    class_id = await _create_class(client, admin_headers, course_id, admin_id)
    student_id = student_user["student_id"]
    enrollment_id = await _create_enrollment(client, admin_headers, student_id, class_id)

    lesson1 = await _create_lesson(client, admin_headers, course_id, {"order": 0, "duration_seconds": 120})
    lesson2 = await _create_lesson(client, admin_headers, course_id, {"order": 1, "duration_seconds": 120})

    # aula 1 não conclui
    r1 = await _complete_lesson(client, lesson1["id"], student_user["headers"], 120)
    assert r1.status_code == 200

    status = await _enrollment_status_db(enrollment_id)
    assert status == EnrollmentStatus.CONFIRMADA
    assert await _certificate_count_db(enrollment_id=enrollment_id) == 0

    # aula 2 conclui
    r2 = await _complete_lesson(client, lesson2["id"], student_user["headers"], 120)
    assert r2.status_code == 200

    status = await _enrollment_status_db(enrollment_id)
    assert status == EnrollmentStatus.CONCLUIDA
    assert await _certificate_count_db(enrollment_id=enrollment_id) == 1


async def test_incomplete_course_does_not_conclude_enrollment(client, admin_headers, student_user):
    course_id = await _create_course(client, admin_headers)
    admin_id = await _get_admin_id(client, admin_headers)
    class_id = await _create_class(client, admin_headers, course_id, admin_id)
    student_id = student_user["student_id"]
    enrollment_id = await _create_enrollment(client, admin_headers, student_id, class_id)

    lesson1 = await _create_lesson(client, admin_headers, course_id, {"order": 0, "duration_seconds": 120})
    await _create_lesson(client, admin_headers, course_id, {"order": 1, "duration_seconds": 120})

    r1 = await _complete_lesson(client, lesson1["id"], student_user["headers"], 120)
    assert r1.status_code == 200

    status = await _enrollment_status_db(enrollment_id)
    assert status == EnrollmentStatus.CONFIRMADA
    assert await _certificate_count_db(enrollment_id=enrollment_id) == 0


async def test_two_enrollments_same_course_only_active_concludes(client, admin_headers, student_user):
    course_id = await _create_course(client, admin_headers)
    admin_id = await _get_admin_id(client, admin_headers)

    class1 = await _create_class(client, admin_headers, course_id, admin_id, status="EM_ANDAMENTO", start_offset_days=1)
    class2 = await _create_class(client, admin_headers, course_id, admin_id, status="ABERTA", start_offset_days=30)

    student_id = student_user["student_id"]
    enrollment1 = await _create_enrollment(client, admin_headers, student_id, class1)
    enrollment2 = await _create_enrollment(client, admin_headers, student_id, class2)

    lesson1 = await _create_lesson(client, admin_headers, course_id, {"order": 0, "duration_seconds": 120})
    lesson2 = await _create_lesson(client, admin_headers, course_id, {"order": 1, "duration_seconds": 120})

    for lesson in [lesson1, lesson2]:
        r = await _complete_lesson(client, lesson["id"], student_user["headers"], 120)
        assert r.status_code == 200

    status1 = await _enrollment_status_db(enrollment1)
    status2 = await _enrollment_status_db(enrollment2)

    assert status1 == EnrollmentStatus.CONCLUIDA
    assert status2 == EnrollmentStatus.CONFIRMADA

    assert await _certificate_count_db(enrollment_id=enrollment1) == 1
    assert await _certificate_count_db(enrollment_id=enrollment2) == 0


async def test_repeat_completion_no_duplicate_certificate(client, admin_headers, student_user):
    course_id = await _create_course(client, admin_headers)
    admin_id = await _get_admin_id(client, admin_headers)
    class_id = await _create_class(client, admin_headers, course_id, admin_id)
    student_id = student_user["student_id"]
    enrollment_id = await _create_enrollment(client, admin_headers, student_id, class_id)

    lesson1 = await _create_lesson(client, admin_headers, course_id, {"order": 0, "duration_seconds": 120})
    lesson2 = await _create_lesson(client, admin_headers, course_id, {"order": 1, "duration_seconds": 120})

    for _ in range(3):
        r1 = await _complete_lesson(client, lesson1["id"], student_user["headers"], 120)
        assert r1.status_code == 200

    r2 = await _complete_lesson(client, lesson2["id"], student_user["headers"], 120)
    assert r2.status_code == 200

    assert await _certificate_count_db(enrollment_id=enrollment_id) == 1
    assert await _enrollment_status_db(enrollment_id) == EnrollmentStatus.CONCLUIDA

    # repetição da última aula
    r3 = await _complete_lesson(client, lesson2["id"], student_user["headers"], 120)
    assert r3.status_code == 200

    assert await _certificate_count_db(enrollment_id=enrollment_id) == 1
    assert await _enrollment_status_db(enrollment_id) == EnrollmentStatus.CONCLUIDA


async def test_certificate_failure_does_not_leave_partial_state(client, admin_headers, student_user, monkeypatch):
    course_id = await _create_course(client, admin_headers)
    admin_id = await _get_admin_id(client, admin_headers)
    class_id = await _create_class(client, admin_headers, course_id, admin_id)
    student_id = student_user["student_id"]
    enrollment_id = await _create_enrollment(client, admin_headers, student_id, class_id)

    lesson1 = await _create_lesson(client, admin_headers, course_id, {"order": 0, "duration_seconds": 120})
    lesson2 = await _create_lesson(client, admin_headers, course_id, {"order": 1, "duration_seconds": 120})

    # conclui aula 1
    r1 = await _complete_lesson(client, lesson1["id"], student_user["headers"], 120)
    assert r1.status_code == 200

    # cria certificado em outra matrícula com número conhecido
    async with AsyncSessionLocal() as db:
        other = (
            await db.execute(select(Enrollment.id).where(Enrollment.student_id == uuid.UUID(student_id)).limit(1))
        ).scalar_one_or_none()
        db.add(
            Certificate(
                enrollment_id=other,
                certificate_number="CERT-DUP",
                validation_code="VAL-DUP",
            )
        )
        await db.commit()

    # força duplicação do número do certificado na próxima emissão
    monkeypatch.setattr("app.api.routes.lessons.generate_certificate_number", lambda: "CERT-DUP")
    monkeypatch.setattr("app.api.routes.lessons.generate_validation_code", lambda: "VAL-NEW")

    # tenta concluir aula 2 e emitir certificado: deve falhar
    r2 = await _complete_lesson(client, lesson2["id"], student_user["headers"], 120)
    assert r2.status_code == 500

    # matrícula não pode ter sido marcada como concluída
    status = await _enrollment_status_db(enrollment_id)
    assert status == EnrollmentStatus.CONFIRMADA

    # progresso da aula 2 não deve ter sido persistido
    assert await _lesson_progress_count(lesson2["id"], student_id) == 0

    # nenhum certificado foi criado para a matrícula deste fluxo
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(func.count(Certificate.id)).where(Certificate.enrollment_id == uuid.UUID(enrollment_id))
        )
        assert result.scalar() == 0
