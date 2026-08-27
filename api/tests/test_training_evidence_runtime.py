import uuid
from datetime import timedelta

import pytest

from app.core.utils import utc_now
from app.services.assessment_service import QUESTION_BANKS
from tests.conftest import make_valid_cpf


async def _create_course(client, admin_headers, *, code, requires_assessment, requires_practical):
    course = await client.post(
        "/api/v1/courses/",
        json={
            "code": code,
            "name": f"Runtime regulatório {code}",
            "category": "Compliance",
            "description": "Fixture de runtime regulatório",
            "carga_horaria": 8,
            "modality": "EAD",
            "tipo_curso": "FORMACAO",
            "price": 0,
        },
        headers=admin_headers,
    )
    assert course.status_code == 201, course.text
    course = course.json()

    professional = await client.post(
        "/api/v1/compliance/professionals",
        json={
            "full_name": f"Profissional {uuid.uuid4().hex[:6]}",
            "cpf": make_valid_cpf(),
            "qualification": "Qualificação de fixture",
            "professional_registration": f"REG-{uuid.uuid4().hex[:6]}",
            "council": "TEST",
            "registration_state": "RJ",
        },
        headers=admin_headers,
    )
    assert professional.status_code == 201, professional.text
    professional = professional.json()

    project = await client.post(
        f"/api/v1/compliance/courses/{course['id']}/projects",
        json={
            "general_objective": "Capacitar para o cenário de teste",
            "specific_objectives": ["Concluir o runtime"],
            "target_audience": "Alunos de homologação",
            "teaching_strategy": "Conteúdo digital com evidências persistentes",
            "syllabus": ["Conteúdo obrigatório"],
            "workload_hours": 8,
            "delivery_mode": "EAD",
            "materials": ["Material de teste"],
            "assessment_methodology": "Avaliação conforme perfil do curso",
        },
        headers=admin_headers,
    )
    assert project.status_code == 201, project.text
    approved = await client.post(
        f"/api/v1/compliance/courses/{course['id']}/projects/{project.json()['id']}/approve",
        json={"approval_notes": "Fixture aprovada"},
        headers=admin_headers,
    )
    assert approved.status_code == 200, approved.text

    profile = await client.put(
        f"/api/v1/compliance/courses/{course['id']}/profile",
        json={
            "regulatory_standard": "TEST-NR",
            "regulatory_version": "runtime-v1",
            "delivery_mode": "EAD",
            "requires_practical_component": requires_practical,
            "requires_final_assessment": requires_assessment,
            "minimum_score": 60 if requires_assessment else None,
            "validity_period_months": 12,
            "certificate_required_fields": ["student_name", "course_name", "workload"],
            "technical_responsible_id": professional["id"],
            "pedagogical_project_version_id": approved.json()["id"],
            "next_compliance_review_at": (utc_now() + timedelta(days=365)).isoformat(),
        },
        headers=admin_headers,
    )
    assert profile.status_code == 200, profile.text

    ready = await client.post(
        f"/api/v1/compliance/courses/{course['id']}/mark-ready",
        headers=admin_headers,
    )
    assert ready.status_code == 200, ready.text
    assert ready.json()["ready"] is True

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

    lesson = await client.post(
        f"/api/v1/lessons/courses/{course['id']}/lessons",
        json={
            "title": "Aula obrigatória",
            "order": 1,
            "content_type": "YOUTUBE",
            "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "duration_seconds": 120,
            "is_required": True,
        },
        headers=admin_headers,
    )
    assert lesson.status_code == 201, lesson.text

    password = "Runtime123!"
    email = f"runtime-{uuid.uuid4().hex[:8]}@example.com"
    student = await client.post(
        "/api/v1/students/",
        json={
            "email": email,
            "full_name": "Aluno Runtime",
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
        "professional": professional,
        "project": approved.json(),
        "class": class_response.json(),
        "lesson": lesson.json(),
        "student": student.json(),
        "enrollment": enrollment.json(),
        "student_headers": student_headers,
        "password": password,
    }


async def _complete_lesson(client, fixture):
    response = await client.post(
        f"/api/v1/lessons/{fixture['lesson']['id']}/progress",
        json={"watched_seconds": 120, "completed": True},
        headers=fixture["student_headers"],
    )
    assert response.status_code == 200, response.text
    assert response.json()["completed"] is True


@pytest.mark.asyncio
async def test_regulatory_assessment_practice_and_confirmation_never_auto_issue_certificate(
    client,
    admin_headers,
):
    fixture = await _create_course(
        client,
        admin_headers,
        code="NR-06-F",
        requires_assessment=True,
        requires_practical=True,
    )
    enrollment_id = fixture["enrollment"]["id"]

    session = await client.post(
        f"/api/v1/training-evidence/enrollments/{enrollment_id}/sessions/start",
        headers={
            **fixture["student_headers"],
            "user-agent": "runtime-regression-test",
            "x-forwarded-for": "203.0.113.10",
        },
    )
    assert session.status_code == 201, session.text

    await _complete_lesson(client, fixture)

    state = await client.get(
        f"/api/v1/training-evidence/enrollments/{enrollment_id}/state",
        headers=fixture["student_headers"],
    )
    assert state.status_code == 200
    assert state.json()["state"] == "ASSESSMENT_PENDING"

    start = await client.post(
        f"/api/v1/assessments/courses/{fixture['course']['id']}/start",
        headers=fixture["student_headers"],
    )
    assert start.status_code == 201, start.text
    assert start.json()["minimum_score"] == 60

    answers = {item["id"]: item["correct"] for item in QUESTION_BANKS["NR-06-F"]}
    submitted = await client.post(
        f"/api/v1/assessments/attempts/{start.json()['attempt_id']}/submit",
        json={"answers": answers},
        headers=fixture["student_headers"],
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["passed"] is True
    assert submitted.json()["minimum_score"] == 60

    state = await client.get(
        f"/api/v1/training-evidence/enrollments/{enrollment_id}/state",
        headers=fixture["student_headers"],
    )
    assert state.json()["state"] == "PRACTICAL_COMPONENT_PENDING"

    premature = await client.post(
        f"/api/v1/training-evidence/enrollments/{enrollment_id}/confirm",
        json={"password": fixture["password"], "declaration_accepted": True},
        headers=fixture["student_headers"],
    )
    assert premature.status_code == 409
    assert premature.json()["detail"]["state"] == "PRACTICAL_COMPONENT_PENDING"

    first_practical = await client.post(
        f"/api/v1/training-evidence/enrollments/{enrollment_id}/practical-records",
        json={
            "instructor_id": fixture["professional"]["id"],
            "result": "UNSATISFACTORY",
            "performed_at": (utc_now() - timedelta(hours=2)).isoformat(),
            "duration_minutes": 60,
            "location": "Laboratório de teste",
            "notes": "Primeira avaliação prática",
        },
        headers=admin_headers,
    )
    assert first_practical.status_code == 201, first_practical.text

    correction = await client.post(
        f"/api/v1/training-evidence/enrollments/{enrollment_id}/practical-records",
        json={
            "instructor_id": fixture["professional"]["id"],
            "result": "SATISFACTORY",
            # Deliberately older performed_at: append order, not event date,
            # determines which correction is current.
            "performed_at": (utc_now() - timedelta(hours=3)).isoformat(),
            "duration_minutes": 60,
            "location": "Laboratório de teste",
            "supersedes_id": first_practical.json()["id"],
            "notes": "Correção administrativa append-only",
        },
        headers=admin_headers,
    )
    assert correction.status_code == 201, correction.text

    state = await client.get(
        f"/api/v1/training-evidence/enrollments/{enrollment_id}/state",
        headers=fixture["student_headers"],
    )
    assert state.json()["state"] == "STUDENT_CONFIRMATION_PENDING"

    confirmed = await client.post(
        f"/api/v1/training-evidence/enrollments/{enrollment_id}/confirm",
        json={"password": fixture["password"], "declaration_accepted": True},
        headers=fixture["student_headers"],
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["state"]["state"] == "CERTIFICATE_PENDING_SIGNATURE"

    legacy_manual = await client.post(
        "/api/v1/certificates/",
        json={"enrollment_id": enrollment_id},
        headers=admin_headers,
    )
    assert legacy_manual.status_code == 409
    assert legacy_manual.json()["detail"]["state"] == "CERTIFICATE_PENDING_SIGNATURE"

    certificates = await client.get("/api/v1/certificates/", headers=admin_headers)
    assert certificates.status_code == 200
    assert not any(item["enrollment_id"] == enrollment_id for item in certificates.json())

    ended = await client.post(
        f"/api/v1/training-evidence/enrollments/{enrollment_id}/sessions/{session.json()['session_id']}/end",
        headers=fixture["student_headers"],
    )
    assert ended.status_code == 200, ended.text

    export = await client.get(
        f"/api/v1/training-evidence/enrollments/{enrollment_id}/export",
        headers=admin_headers,
    )
    assert export.status_code == 200, export.text
    assert export.json()["state"]["state"] == "CERTIFICATE_PENDING_SIGNATURE"
    event_types = {item["event_type"] for item in export.json()["events"]}
    assert {
        "SESSION_STARTED",
        "SESSION_ENDED",
        "PROGRESS_UPDATED",
        "LESSON_COMPLETED",
        "ASSESSMENT_STARTED",
        "ASSESSMENT_SUBMITTED",
        "PRACTICAL_COMPONENT_RECORDED",
        "STUDENT_CONFIRMATION",
        "STATE_TRANSITION",
        "EVIDENCE_EXPORTED",
    }.issubset(event_types)
    fingerprints = [
        item["client_fingerprint"]
        for item in export.json()["events"]
        if item["client_fingerprint"]
    ]
    assert fingerprints
    assert all(len(item) == 64 for item in fingerprints)
    assert all("203.0.113.10" not in str(item) for item in export.json()["events"])


@pytest.mark.asyncio
async def test_regulatory_course_without_assessment_can_confirm_without_fake_attempt(
    client,
    admin_headers,
):
    fixture = await _create_course(
        client,
        admin_headers,
        code=f"NO-ASSESS-{uuid.uuid4().hex[:6].upper()}",
        requires_assessment=False,
        requires_practical=False,
    )
    enrollment_id = fixture["enrollment"]["id"]
    await _complete_lesson(client, fixture)

    state = await client.get(
        f"/api/v1/training-evidence/enrollments/{enrollment_id}/state",
        headers=fixture["student_headers"],
    )
    assert state.status_code == 200
    assert state.json()["state"] == "STUDENT_CONFIRMATION_PENDING"

    confirmed = await client.post(
        f"/api/v1/training-evidence/enrollments/{enrollment_id}/confirm",
        json={"password": fixture["password"], "declaration_accepted": True},
        headers=fixture["student_headers"],
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["state"]["state"] == "CERTIFICATE_PENDING_SIGNATURE"

    again = await client.post(
        f"/api/v1/training-evidence/enrollments/{enrollment_id}/confirm",
        json={"password": fixture["password"], "declaration_accepted": True},
        headers=fixture["student_headers"],
    )
    assert again.status_code == 200, again.text
    assert again.json()["state"]["state"] == "CERTIFICATE_PENDING_SIGNATURE"


@pytest.mark.asyncio
async def test_training_ledger_rejects_non_regulatory_enrollment(client, student_user):
    enrollments = await client.get(
        "/api/v1/enrollments/me",
        headers=student_user["headers"],
    )
    assert enrollments.status_code == 200
    assert enrollments.json()
    enrollment_id = enrollments.json()[0]["id"]

    session = await client.post(
        f"/api/v1/training-evidence/enrollments/{enrollment_id}/sessions/start",
        headers=student_user["headers"],
    )
    assert session.status_code == 409
    assert "not enabled" in session.json()["detail"]


@pytest.mark.asyncio
async def test_student_cannot_export_regulatory_evidence(client, admin_headers):
    fixture = await _create_course(
        client,
        admin_headers,
        code=f"NO-EXPORT-{uuid.uuid4().hex[:6].upper()}",
        requires_assessment=False,
        requires_practical=False,
    )
    response = await client.get(
        f"/api/v1/training-evidence/enrollments/{fixture['enrollment']['id']}/export",
        headers=fixture["student_headers"],
    )
    assert response.status_code == 403
