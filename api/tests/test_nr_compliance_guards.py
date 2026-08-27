from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.utils import utc_now
from app.models.compliance import CourseComplianceProfile
from tests.conftest import make_valid_cpf


async def _create_regulatory_course(client, admin_headers):
    response = await client.post(
        "/api/v1/courses/",
        json={
            "code": "NR-06-F",
            "name": "NR-06 Formação",
            "category": "Segurança",
            "description": "Curso regulatório de teste",
            "carga_horaria": 8,
            "modality": "EAD",
            "tipo_curso": "FORMACAO",
            "price": 100.0,
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_professional(client, admin_headers):
    response = await client.post(
        "/api/v1/compliance/professionals",
        json={
            "full_name": "Responsável Técnico Teste",
            "cpf": make_valid_cpf(),
            "qualification": "Engenheiro de Segurança do Trabalho",
            "professional_registration": "REG-123",
            "council": "CREA",
            "registration_state": "RJ",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_and_approve_project(client, admin_headers, course_id):
    project = await client.post(
        f"/api/v1/compliance/courses/{course_id}/projects",
        json={
            "general_objective": "Capacitar trabalhadores",
            "specific_objectives": ["Reconhecer riscos"],
            "target_audience": "Trabalhadores expostos",
            "teaching_strategy": "Aulas EAD e avaliação final",
            "syllabus": ["Introdução", "Responsabilidades", "Uso correto"],
            "workload_hours": 8,
            "delivery_mode": "EAD",
            "materials": ["Apostila"],
            "assessment_methodology": "Avaliação objetiva com aproveitamento mínimo",
        },
        headers=admin_headers,
    )
    assert project.status_code == 201, project.text
    approved = await client.post(
        f"/api/v1/compliance/courses/{course_id}/projects/{project.json()['id']}/approve",
        json={"approval_notes": "Revisado para homologação"},
        headers=admin_headers,
    )
    assert approved.status_code == 200, approved.text
    return approved.json()


async def _mark_ready(
    client,
    admin_headers,
    *,
    course_id,
    professional_id,
    project_id,
    next_review,
):
    profile = await client.put(
        f"/api/v1/compliance/courses/{course_id}/profile",
        json={
            "regulatory_standard": "NR-06",
            "regulatory_version": "homologacao-v1",
            "delivery_mode": "EAD",
            "requires_practical_component": False,
            "requires_final_assessment": True,
            "minimum_score": 60,
            "validity_period_months": 24,
            "certificate_required_fields": ["student_name", "course_name", "workload"],
            "technical_responsible_id": professional_id,
            "pedagogical_project_version_id": project_id,
            "next_compliance_review_at": next_review.isoformat(),
        },
        headers=admin_headers,
    )
    assert profile.status_code == 200, profile.text
    ready = await client.post(
        f"/api/v1/compliance/courses/{course_id}/mark-ready",
        headers=admin_headers,
    )
    assert ready.status_code == 200, ready.text
    assert ready.json()["ready"] is True


async def _class_payload(client, admin_headers, course_id):
    me = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert me.status_code == 200
    start = utc_now().date() + timedelta(days=1)
    return {
        "course_id": course_id,
        "responsible_admin_id": me.json()["id"],
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=10)).isoformat(),
        "max_students": 20,
        "status": "ABERTA",
        "description": "Turma regulatória",
    }


@pytest.mark.asyncio
async def test_ready_course_pins_approved_project_when_class_is_created(client, admin_headers):
    course = await _create_regulatory_course(client, admin_headers)
    professional = await _create_professional(client, admin_headers)
    project = await _create_and_approve_project(client, admin_headers, course["id"])
    await _mark_ready(
        client,
        admin_headers,
        course_id=course["id"],
        professional_id=professional["id"],
        project_id=project["id"],
        next_review=utc_now() + timedelta(days=180),
    )

    created = await client.post(
        "/api/v1/classes/",
        json=await _class_payload(client, admin_headers, course["id"]),
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["pedagogical_project_version_id"] == project["id"]


@pytest.mark.asyncio
async def test_professional_change_reopens_review_and_blocks_new_class(client, admin_headers):
    course = await _create_regulatory_course(client, admin_headers)
    professional = await _create_professional(client, admin_headers)
    project = await _create_and_approve_project(client, admin_headers, course["id"])
    await _mark_ready(
        client,
        admin_headers,
        course_id=course["id"],
        professional_id=professional["id"],
        project_id=project["id"],
        next_review=utc_now() + timedelta(days=180),
    )

    changed = await client.patch(
        f"/api/v1/compliance/professionals/{professional['id']}",
        json={"qualification": "Qualificação revisada após a aprovação"},
        headers=admin_headers,
    )
    assert changed.status_code == 200, changed.text

    readiness = await client.get(
        f"/api/v1/compliance/courses/{course['id']}/readiness",
        headers=admin_headers,
    )
    assert readiness.status_code == 200
    assert readiness.json()["ready"] is False
    assert readiness.json()["status"] == "REVIEW_REQUIRED"

    blocked = await client.post(
        "/api/v1/classes/",
        json=await _class_payload(client, admin_headers, course["id"]),
        headers=admin_headers,
    )
    assert blocked.status_code == 409
    assert "compliance-ready" in blocked.json()["detail"]


@pytest.mark.asyncio
async def test_expired_review_is_not_ready_and_blocks_new_class(client, admin_headers):
    course = await _create_regulatory_course(client, admin_headers)
    professional = await _create_professional(client, admin_headers)
    project = await _create_and_approve_project(client, admin_headers, course["id"])
    await _mark_ready(
        client,
        admin_headers,
        course_id=course["id"],
        professional_id=professional["id"],
        project_id=project["id"],
        next_review=utc_now() + timedelta(days=180),
    )

    # Simulate time passing after an originally valid approval. The input API
    # rejects dates already expired, so runtime expiry is exercised directly.
    async with AsyncSessionLocal() as session:
        profile = (
            await session.execute(
                select(CourseComplianceProfile).where(
                    CourseComplianceProfile.course_id == course["id"]
                )
            )
        ).scalar_one()
        profile.next_compliance_review_at = utc_now() - timedelta(seconds=1)
        await session.commit()

    readiness = await client.get(
        f"/api/v1/compliance/courses/{course['id']}/readiness",
        headers=admin_headers,
    )
    assert readiness.status_code == 200
    assert readiness.json()["ready"] is False
    assert "Compliance review date has expired" in readiness.json()["blockers"]

    blocked = await client.post(
        "/api/v1/classes/",
        json=await _class_payload(client, admin_headers, course["id"]),
        headers=admin_headers,
    )
    assert blocked.status_code == 409
    assert "missing or expired" in blocked.json()["detail"]


@pytest.mark.asyncio
async def test_profile_rejects_review_date_already_expired(client, admin_headers):
    course = await _create_regulatory_course(client, admin_headers)
    professional = await _create_professional(client, admin_headers)
    project = await _create_and_approve_project(client, admin_headers, course["id"])

    response = await client.put(
        f"/api/v1/compliance/courses/{course['id']}/profile",
        json={
            "regulatory_standard": "NR-06",
            "regulatory_version": "homologacao-v1",
            "delivery_mode": "EAD",
            "requires_practical_component": False,
            "requires_final_assessment": True,
            "minimum_score": 60,
            "certificate_required_fields": ["student_name"],
            "technical_responsible_id": professional["id"],
            "pedagogical_project_version_id": project["id"],
            "next_compliance_review_at": (utc_now() - timedelta(days=1)).isoformat(),
        },
        headers=admin_headers,
    )
    assert response.status_code == 422
