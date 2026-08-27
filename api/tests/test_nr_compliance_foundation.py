import uuid
from datetime import timedelta

import pytest

from app.core.utils import utc_now


async def _admin_id(client, admin_headers):
    response = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert response.status_code == 200, response.text
    return response.json()["id"]


async def _create_course(
    client,
    admin_headers,
    *,
    code: str,
    workload: int = 8,
    modality: str = "EAD",
):
    response = await client.post(
        "/api/v1/courses/",
        json={
            "code": code,
            "name": f"Curso Compliance {code}",
            "category": "Teste de compliance",
            "carga_horaria": workload,
            "modality": modality,
            "price": 100.0,
            "description": "Curso técnico usado somente em regressão automatizada.",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_professional(client, admin_headers, *, cpf="52998224725"):
    response = await client.post(
        "/api/v1/compliance/professionals",
        json={
            "full_name": "Profissional Teste",
            "cpf": cpf,
            "qualification": "Qualificação de teste sem alegação regulatória real",
            "professional_registration": "TEST-001",
            "council": "TEST",
            "registration_state": "SP",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_project(
    client,
    admin_headers,
    course_id,
    *,
    workload=8,
    modality="EAD",
):
    response = await client.post(
        f"/api/v1/compliance/courses/{course_id}/projects",
        json={
            "general_objective": "Objetivo de teste",
            "specific_objectives": ["Objetivo específico de teste"],
            "target_audience": "Público de teste",
            "teaching_strategy": "Estratégia pedagógica de teste",
            "syllabus": ["Conteúdo programático de teste"],
            "workload_hours": workload,
            "delivery_mode": modality,
            "materials": ["Material de teste"],
            "assessment_methodology": "Metodologia de avaliação de teste",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _approve_project(client, admin_headers, course_id, project_id):
    response = await client.post(
        f"/api/v1/compliance/courses/{course_id}/projects/{project_id}/approve",
        json={"approval_notes": "Aprovação automatizada de fixture de teste."},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _upsert_profile(
    client,
    admin_headers,
    course_id,
    professional_id,
    project_id,
    *,
    requires_assessment=True,
    requires_practical=False,
    minimum_score=60.0,
):
    payload = {
        "regulatory_standard": "TEST-NR",
        "regulatory_version": "fixture-v1",
        "delivery_mode": "EAD",
        "requires_practical_component": requires_practical,
        "requires_final_assessment": requires_assessment,
        "minimum_score": minimum_score if requires_assessment else None,
        "validity_period_months": 12,
        "prerequisites": "Fixture sem afirmação normativa real",
        "certificate_required_fields": ["student_name", "course_name"],
        "technical_responsible_id": professional_id,
        "pedagogical_project_version_id": project_id,
        "next_compliance_review_at": "2027-08-27T00:00:00",
    }
    return await client.put(
        f"/api/v1/compliance/courses/{course_id}/profile",
        json=payload,
        headers=admin_headers,
    )


@pytest.mark.asyncio
async def test_compliance_ready_pins_approved_project_and_new_version_requires_review(
    client,
    admin_headers,
):
    course = await _create_course(client, admin_headers, code="NR-06-F")
    professional = await _create_professional(client, admin_headers)
    project_v1 = await _create_project(client, admin_headers, course["id"])
    assert project_v1["version"] == 1
    approved_v1 = await _approve_project(
        client,
        admin_headers,
        course["id"],
        project_v1["id"],
    )
    assert approved_v1["status"] == "APPROVED"

    profile = await _upsert_profile(
        client,
        admin_headers,
        course["id"],
        professional["id"],
        project_v1["id"],
    )
    assert profile.status_code == 200, profile.text
    assert profile.json()["status"] == "DRAFT"

    ready = await client.post(
        f"/api/v1/compliance/courses/{course['id']}/mark-ready",
        headers=admin_headers,
    )
    assert ready.status_code == 200, ready.text
    assert ready.json()["ready"] is True
    assert ready.json()["status"] == "COMPLIANCE_READY"

    admin_id = await _admin_id(client, admin_headers)
    today = utc_now().date()
    class_response = await client.post(
        "/api/v1/classes/",
        json={
            "course_id": course["id"],
            "responsible_admin_id": admin_id,
            "start_date": (today + timedelta(days=1)).isoformat(),
            "end_date": (today + timedelta(days=30)).isoformat(),
            "max_students": 20,
            "status": "ABERTA",
            "description": "Turma regulatória de teste",
        },
        headers=admin_headers,
    )
    assert class_response.status_code == 201, class_response.text
    assert class_response.json()["pedagogical_project_version_id"] == project_v1["id"]

    immutable = await client.patch(
        f"/api/v1/compliance/courses/{course['id']}/projects/{project_v1['id']}",
        json={"general_objective": "Tentativa de reescrever histórico"},
        headers=admin_headers,
    )
    assert immutable.status_code == 409

    project_v2 = await _create_project(client, admin_headers, course["id"])
    assert project_v2["version"] == 2
    approved_v2 = await _approve_project(
        client,
        admin_headers,
        course["id"],
        project_v2["id"],
    )
    assert approved_v2["status"] == "APPROVED"

    current_profile = await client.get(
        f"/api/v1/compliance/courses/{course['id']}/profile",
        headers=admin_headers,
    )
    assert current_profile.status_code == 200
    assert current_profile.json()["status"] == "REVIEW_REQUIRED"
    assert current_profile.json()["pedagogical_project_version_id"] == project_v1["id"]

    blocked_class = await client.post(
        "/api/v1/classes/",
        json={
            "course_id": course["id"],
            "responsible_admin_id": admin_id,
            "start_date": (today + timedelta(days=2)).isoformat(),
            "end_date": (today + timedelta(days=31)).isoformat(),
            "max_students": 20,
            "status": "ABERTA",
        },
        headers=admin_headers,
    )
    assert blocked_class.status_code == 409


@pytest.mark.asyncio
async def test_readiness_blocks_missing_assessment_bank_but_supports_practical_runtime(
    client,
    admin_headers,
):
    course = await _create_course(
        client,
        admin_headers,
        code=f"TEST-{uuid.uuid4().hex[:8].upper()}",
    )
    professional = await _create_professional(client, admin_headers)
    project = await _create_project(client, admin_headers, course["id"])
    await _approve_project(client, admin_headers, course["id"], project["id"])

    profile = await _upsert_profile(
        client,
        admin_headers,
        course["id"],
        professional["id"],
        project["id"],
        requires_assessment=True,
        requires_practical=True,
    )
    assert profile.status_code == 200, profile.text

    ready = await client.post(
        f"/api/v1/compliance/courses/{course['id']}/mark-ready",
        headers=admin_headers,
    )
    assert ready.status_code == 409, ready.text
    blockers = ready.json()["detail"]["blockers"]
    assert any("assessment bank" in item for item in blockers)
    assert not any("Practical component tracking" in item for item in blockers)


@pytest.mark.asyncio
async def test_compliance_profile_rejects_threshold_not_enforced_by_engine(
    client,
    admin_headers,
):
    course = await _create_course(client, admin_headers, code="NR-06-F")
    professional = await _create_professional(client, admin_headers)
    project = await _create_project(client, admin_headers, course["id"])

    response = await _upsert_profile(
        client,
        admin_headers,
        course["id"],
        professional["id"],
        project["id"],
        minimum_score=70.0,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_training_professional_cpf_and_duplicate_are_strict(
    client,
    admin_headers,
):
    invalid = await client.post(
        "/api/v1/compliance/professionals",
        json={
            "full_name": "Profissional Inválido",
            "cpf": "11111111111",
            "qualification": "Teste",
        },
        headers=admin_headers,
    )
    assert invalid.status_code == 400

    professional = await _create_professional(client, admin_headers)
    assert professional["cpf"] == "52998224725"

    duplicate = await client.post(
        "/api/v1/compliance/professionals",
        json={
            "full_name": "Mesmo CPF",
            "cpf": "529.982.247-25",
            "qualification": "Outra qualificação de teste",
        },
        headers=admin_headers,
    )
    assert duplicate.status_code == 409


@pytest.mark.asyncio
async def test_student_cannot_access_compliance_administration(client, student_user):
    response = await client.get(
        "/api/v1/compliance/professionals",
        headers=student_user["headers"],
    )
    assert response.status_code == 403
