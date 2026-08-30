"""End-to-end eligibility and status tests for the final assessment flow.

Covers the regression where a student with 100% / all required lessons
completed did not see the final assessment because the status endpoint
and the frontend disagreed about eligibility. The eligibility rule must
be driven by the precise required-lessons count (not a rounded
percentage), and completing the last required lesson must immediately
flip ``lessons_complete`` to true without a manual refresh.
"""

import uuid
from datetime import timedelta

import pytest

from app.core.utils import utc_now
from app.services.assessment_service import QUESTION_BANKS
from tests.conftest import make_valid_cpf


async def _build_course_with_lessons(
    client,
    admin_headers,
    *,
    code,
    required_lessons,
    optional_lessons=0,
    optional_first=False,
):
    """Create a course (code backed by a question bank), a class, a student
    enrolled, and the requested number of required + optional lessons.

    Returns a dict with the ids needed to drive the assessment flow.
    """
    course = await client.post(
        "/api/v1/courses/",
        json={
            "code": code,
            "name": f"Curso elegibilidade {code}",
            "category": "Compliance",
            "description": "Fixture de elegibilidade de avaliação",
            "carga_horaria": 8,
            "modality": "EAD",
            "tipo_curso": "FORMACAO",
            "price": 0,
        },
        headers=admin_headers,
    )
    assert course.status_code == 201, course.text
    course = course.json()

    me = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert me.status_code == 200
    today = utc_now().date()
    class_response = await client.post(
        "/api/v1/classes/",
        json={
            "course_id": course["id"],
            "responsible_admin_id": me.json()["id"],
            "start_date": (today + timedelta(days=1)).isoformat(),
            "end_date": (today + timedelta(days=30)).isoformat(),
            "max_students": 20,
            "status": "ABERTA",
        },
        headers=admin_headers,
    )
    assert class_response.status_code == 201, class_response.text

    lessons = []
    order = 1

    def _make_lesson_payload(title, is_required):
        return {
            "title": title,
            "order": order,
            "content_type": "YOUTUBE",
            "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "duration_seconds": 120,
            "is_required": is_required,
        }

    async def _create_lesson(title, is_required):
        nonlocal order
        lesson = await client.post(
            f"/api/v1/lessons/courses/{course['id']}/lessons",
            json=_make_lesson_payload(title, is_required),
            headers=admin_headers,
        )
        assert lesson.status_code == 201, lesson.text
        result = lesson.json()
        order += 1
        return result

    optional_specs = [(f"Aula opcional {i + 1}", False) for i in range(optional_lessons)]
    required_specs = [(f"Aula obrigatória {i + 1}", True) for i in range(required_lessons)]
    specs = (optional_specs + required_specs) if optional_first else (required_specs + optional_specs)
    for title, is_required in specs:
        lessons.append(await _create_lesson(title, is_required))

    password = "Elig123!"
    email = f"elig-{uuid.uuid4().hex[:8]}@example.com"
    student = await client.post(
        "/api/v1/students/",
        json={
            "email": email,
            "full_name": "Aluno Elegibilidade",
            "password": password,
            "cpf": make_valid_cpf(),
        },
        headers=admin_headers,
    )
    assert student.status_code == 201, student.text
    enrollment = await client.post(
        "/api/v1/enrollments/",
        json={
            "student_id": student.json()["id"],
            "class_id": class_response.json()["id"],
            "price": 0,
            "status": "CONFIRMADA",
            "source": "INDIVIDUAL",
        },
        headers=admin_headers,
    )
    assert enrollment.status_code == 201, enrollment.text

    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": password},
    )
    assert login.status_code == 200, login.text
    student_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    return {
        "course": course,
        "lessons": lessons,
        "required_lessons": required_lessons,
        "student_headers": student_headers,
        "password": password,
    }


async def _complete_lesson(client, fixture, lesson, *, assessment_route=True):
    """Mark a lesson complete via the assessment or legacy progress route.

    Assessment-backed courses (code in QUESTION_BANKS) use the assessment
    progress route; courses without a final assessment use the legacy
    lessons progress route.
    """
    endpoint = (
        f"/api/v1/assessments/lessons/{lesson['id']}/progress"
        if assessment_route
        else f"/api/v1/lessons/{lesson['id']}/progress"
    )
    response = await client.post(
        endpoint,
        json={"watched_seconds": 120, "completed": True},
        headers=fixture["student_headers"],
    )
    assert response.status_code == 200, response.text
    assert response.json()["completed"] is True


async def _status(client, fixture):
    response = await client.get(
        f"/api/v1/assessments/courses/{fixture['course']['id']}/status",
        headers=fixture["student_headers"],
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_course_without_assessment_returns_required_false(client, admin_headers):
    """A course whose code has no question bank must report required=False,
    distinct from a locked or errored assessment."""
    fixture = await _build_course_with_lessons(
        client, admin_headers, code=f"NO-ASSESS-{uuid.uuid4().hex[:4].upper()}", required_lessons=2
    )
    # Complete every required lesson via the legacy route (no assessment
    # configured for this course) — still no assessment configured.
    for lesson in fixture["lessons"]:
        await _complete_lesson(client, fixture, lesson, assessment_route=False)
    status = await _status(client, fixture)
    assert status["required"] is False
    assert status["lessons_complete"] is False
    assert status["passed"] is False


@pytest.mark.asyncio
async def test_eligibility_progresses_with_required_lessons(client, admin_headers):
    """0/6 → not eligible; 5/6 → not eligible; 6/6 → eligible immediately."""
    fixture = await _build_course_with_lessons(
        client, admin_headers, code="NR-10-B", required_lessons=6
    )

    status = await _status(client, fixture)
    assert status["required"] is True
    assert status["lessons_complete"] is False

    for index, lesson in enumerate(fixture["lessons"]):
        await _complete_lesson(client, fixture, lesson)
        status = await _status(client, fixture)
        if index < 5:
            assert status["lessons_complete"] is False, (
                f"should remain locked after {index + 1}/6 lessons"
            )
        else:
            assert status["lessons_complete"] is True, (
                "completing the last required lesson must flip eligibility immediately"
            )


@pytest.mark.asyncio
async def test_last_required_lesson_unlocks_start(client, admin_headers):
    """After the 6th required lesson, /start must succeed (no refresh needed)."""
    fixture = await _build_course_with_lessons(
        client, admin_headers, code="NR-10-B", required_lessons=6
    )
    for lesson in fixture["lessons"][:-1]:
        await _complete_lesson(client, fixture, lesson)
    start_before = await client.post(
        f"/api/v1/assessments/courses/{fixture['course']['id']}/start",
        headers=fixture["student_headers"],
    )
    assert start_before.status_code == 409

    await _complete_lesson(client, fixture, fixture["lessons"][-1])
    start_after = await client.post(
        f"/api/v1/assessments/courses/{fixture['course']['id']}/start",
        headers=fixture["student_headers"],
    )
    assert start_after.status_code == 201, start_after.text
    assert len(start_after.json()["questions"]) == len(QUESTION_BANKS["NR-10-B"])


@pytest.mark.asyncio
async def test_optional_lessons_do_not_unlock_assessment(client, admin_headers):
    """Completing only optional lessons must not flip eligibility."""
    fixture = await _build_course_with_lessons(
        client, admin_headers, code="NR-10-B", required_lessons=2, optional_lessons=3,
        optional_first=True,
    )
    optional = [lesson for lesson in fixture["lessons"] if not lesson["is_required"]]
    for lesson in optional:
        await _complete_lesson(client, fixture, lesson)
    status = await _status(client, fixture)
    assert status["required"] is True
    assert status["lessons_complete"] is False


@pytest.mark.asyncio
async def test_passed_attempt_status(client, admin_headers):
    """A passing attempt must surface as passed=true in the status payload."""
    fixture = await _build_course_with_lessons(
        client, admin_headers, code="NR-10-B", required_lessons=1
    )
    await _complete_lesson(client, fixture, fixture["lessons"][0])

    started = await client.post(
        f"/api/v1/assessments/courses/{fixture['course']['id']}/start",
        headers=fixture["student_headers"],
    )
    assert started.status_code == 201
    answers = {item["id"]: item["correct"] for item in QUESTION_BANKS["NR-10-B"]}
    submitted = await client.post(
        f"/api/v1/assessments/attempts/{started.json()['attempt_id']}/submit",
        json={"answers": answers},
        headers=fixture["student_headers"],
    )
    assert submitted.status_code == 200
    assert submitted.json()["passed"] is True

    status = await _status(client, fixture)
    assert status["passed"] is True
    assert status["passed_attempt_id"] is not None
    assert status["attempts"] == 1


@pytest.mark.asyncio
async def test_failed_attempt_allows_new_attempt(client, admin_headers):
    """A failed attempt with no artificial cap must allow starting again."""
    fixture = await _build_course_with_lessons(
        client, admin_headers, code="NR-10-B", required_lessons=1
    )
    await _complete_lesson(client, fixture, fixture["lessons"][0])

    started = await client.post(
        f"/api/v1/assessments/courses/{fixture['course']['id']}/start",
        headers=fixture["student_headers"],
    )
    assert started.status_code == 201
    bank = QUESTION_BANKS["NR-10-B"]
    wrong = {item["id"]: (item["correct"] + 1) % len(item["options"]) for item in bank}
    submitted = await client.post(
        f"/api/v1/assessments/attempts/{started.json()['attempt_id']}/submit",
        json={"answers": wrong},
        headers=fixture["student_headers"],
    )
    assert submitted.status_code == 200
    assert submitted.json()["passed"] is False

    status = await _status(client, fixture)
    assert status["passed"] is False
    assert status["attempts"] == 1

    retry = await client.post(
        f"/api/v1/assessments/courses/{fixture['course']['id']}/start",
        headers=fixture["student_headers"],
    )
    assert retry.status_code == 201
    assert retry.json()["attempt_number"] == 2


@pytest.mark.asyncio
async def test_status_endpoint_is_idempotent_under_normal_call_volume(client, admin_headers):
    """A normal volume of status lookups (as the player emits) must not cause
    incorrect behavior. Guards against request-storm regressions on the read
    path."""
    fixture = await _build_course_with_lessons(
        client, admin_headers, code="NR-10-B", required_lessons=1
    )
    await _complete_lesson(client, fixture, fixture["lessons"][0])
    # Emulate the player's repeated status checks (well below any abuse limit).
    for _ in range(10):
        status = await _status(client, fixture)
        assert status["required"] is True
        assert status["lessons_complete"] is True
