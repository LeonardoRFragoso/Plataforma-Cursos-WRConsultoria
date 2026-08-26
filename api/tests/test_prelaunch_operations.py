import uuid
from datetime import timedelta

import pytest

from app.core.utils import utc_now
from tests.conftest import make_valid_cpf


async def _create_course_and_class(client, admin_headers, *, price=320.0, validity_days=365):
    course = await client.post(
        "/api/v1/courses/",
        json={
            "code": f"OPS-{uuid.uuid4().hex[:8].upper()}",
            "name": "Curso Operacional Integrado",
            "category": "Segurança",
            "description": "Curso para jornada operacional pré-lançamento",
            "carga_horaria": 16,
            "modality": "EAD",
            "tipo_curso": "FORMACAO",
            "price": price,
            "certificate_validity_days": validity_days,
        },
        headers=admin_headers,
    )
    assert course.status_code == 201, course.text
    me = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert me.status_code == 200
    start = utc_now().date() + timedelta(days=1)
    class_response = await client.post(
        "/api/v1/classes/",
        json={
            "course_id": course.json()["id"],
            "responsible_admin_id": me.json()["id"],
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=20)).isoformat(),
            "max_students": 30,
            "status": "ABERTA",
            "description": "Turma Operacional",
        },
        headers=admin_headers,
    )
    assert class_response.status_code == 201, class_response.text
    return course.json(), class_response.json()


async def _create_company(client, admin_headers):
    response = await client.post(
        "/api/v1/companies/",
        json={
            "legal_name": f"Empresa Operacional {uuid.uuid4().hex[:6]}",
            "trade_name": "Empresa OPS",
            "cnpj": f"{uuid.uuid4().int % 10**14:014d}",
            "rh_name": "RH Operacional",
            "rh_email": f"rh-{uuid.uuid4().hex[:6]}@example.com",
            "rh_phone": "21999999999",
            "billing_email": f"financeiro-{uuid.uuid4().hex[:6]}@example.com",
            "contract_reference": "CONTRATO-OPS",
            "status": "ACTIVE",
            "notes": "Conta de homologação",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_corporate_request_pipeline_and_company_operations(client, admin_headers):
    lead = await client.post(
        "/api/v1/corporate/requests",
        json={
            "company_name": "Indústria Teste",
            "cnpj": "12345678000199",
            "contact_name": "Responsável RH",
            "contact_email": "rh.pipeline@example.com",
            "contact_phone": "21988887777",
            "course_interest": "NR-10",
            "employee_count": 12,
            "message": "Treinamento para nova equipe",
        },
    )
    assert lead.status_code == 201, lead.text
    lead_id = lead.json()["id"]

    listed = await client.get("/api/v1/corporate/requests", headers=admin_headers)
    assert listed.status_code == 200
    assert any(item["id"] == lead_id for item in listed.json())

    updated = await client.patch(
        f"/api/v1/corporate/requests/{lead_id}",
        json={"status": "QUALIFIED", "admin_notes": "Escopo validado"},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "QUALIFIED"

    company = await _create_company(client, admin_headers)
    _course, class_obj = await _create_course_and_class(client, admin_headers)

    invite = await client.post(
        f"/api/v1/corporate/companies/{company['id']}/invites",
        json={
            "email": f"colaborador-{uuid.uuid4().hex[:8]}@example.com",
            "full_name": "Colaborador Corporativo",
            "cpf": make_valid_cpf(),
            "phone": "21977776666",
        },
        headers=admin_headers,
    )
    assert invite.status_code == 201, invite.text
    invite_body = invite.json()
    student_id = invite_body["student_id"]
    assert student_id

    if invite_body.get("activation_token"):
        activated = await client.post(
            "/api/v1/auth/activate",
            json={"token": invite_body["activation_token"], "new_password": "Corporate123!"},
        )
        assert activated.status_code == 200, activated.text

    invites = await client.get(
        f"/api/v1/corporate/companies/{company['id']}/invites",
        headers=admin_headers,
    )
    assert invites.status_code == 200
    assert any(item["student_id"] == student_id for item in invites.json())

    seats = await client.post(
        f"/api/v1/corporate/companies/{company['id']}/seat-allocations",
        json={"class_id": class_obj["id"], "seats_reserved": 5, "notes": "Contrato anual"},
        headers=admin_headers,
    )
    assert seats.status_code == 200, seats.text
    assert seats.json()["seats_available"] == 5

    bulk = await client.post(
        f"/api/v1/corporate/companies/{company['id']}/bulk-enroll",
        json={"class_id": class_obj["id"], "student_ids": [student_id]},
        headers=admin_headers,
    )
    assert bulk.status_code == 200, bulk.text
    assert bulk.json()["created"] == 1
    assert len(bulk.json()["enrollment_ids"]) == 1

    report = await client.get(
        f"/api/v1/corporate/companies/{company['id']}/training-report",
        headers=admin_headers,
    )
    assert report.status_code == 200
    assert report.json()["total_employees"] == 1
    assert report.json()["total_enrollments"] == 1

    allocations = await client.get(
        f"/api/v1/corporate/companies/{company['id']}/seat-allocations",
        headers=admin_headers,
    )
    assert allocations.status_code == 200
    assert allocations.json()[0]["seats_used"] == 1

    offboard = await client.post(
        f"/api/v1/corporate/companies/{company['id']}/employees/{student_id}/offboard",
        json={"deactivate_account": False, "cancel_active_corporate_enrollments": True},
        headers=admin_headers,
    )
    assert offboard.status_code == 200
    assert offboard.json()["offboarded"] is True
    assert offboard.json()["corporate_enrollments_cancelled"] == 1


@pytest.mark.asyncio
async def test_corporate_invite_can_be_revoked(client, admin_headers):
    company = await _create_company(client, admin_headers)
    invite = await client.post(
        f"/api/v1/corporate/companies/{company['id']}/invites",
        json={
            "email": f"revogar-{uuid.uuid4().hex[:8]}@example.com",
            "full_name": "Convite Revogável",
            "cpf": make_valid_cpf(),
        },
        headers=admin_headers,
    )
    assert invite.status_code == 201
    revoked = await client.post(
        f"/api/v1/corporate/companies/{company['id']}/invites/{invite.json()['id']}/revoke",
        headers=admin_headers,
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "REVOKED"


@pytest.mark.asyncio
async def test_trusted_certificate_revoke_reissue_and_validation(client, admin_headers):
    _course, class_obj = await _create_course_and_class(client, admin_headers, validity_days=30)
    student = await client.post(
        "/api/v1/students/",
        json={
            "email": f"cert-{uuid.uuid4().hex[:8]}@example.com",
            "full_name": "Aluno Certificado",
            "password": "student123",
            "cpf": make_valid_cpf(),
            "class_id": class_obj["id"],
        },
        headers=admin_headers,
    )
    assert student.status_code == 201, student.text
    enrollments = await client.get("/api/v1/enrollments/", headers=admin_headers)
    enrollment = next(item for item in enrollments.json() if item["student_id"] == student.json()["id"])
    completed = await client.put(
        f"/api/v1/enrollments/{enrollment['id']}",
        json={"status": "CONCLUIDA"},
        headers=admin_headers,
    )
    assert completed.status_code == 200

    issued = await client.post(
        "/api/v1/certificates/",
        json={"enrollment_id": enrollment["id"]},
        headers=admin_headers,
    )
    assert issued.status_code == 201, issued.text
    first = issued.json()
    assert first["status"] == "ACTIVE"
    assert first["version"] == 1
    assert first["content_hash"]
    assert first["expires_at"]

    valid = await client.post(
        "/api/v1/certificates/validate",
        json={"validation_code": first["validation_code"]},
    )
    assert valid.status_code == 200
    assert valid.json()["valid"] is True
    assert valid.json()["status"] == "ACTIVE"

    revoked = await client.post(
        f"/api/v1/certificates/{first['id']}/revoke",
        json={"reason": "Correção administrativa de dados"},
        headers=admin_headers,
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "REVOKED"

    old_validation = await client.post(
        "/api/v1/certificates/validate",
        json={"validation_code": first["validation_code"]},
    )
    assert old_validation.json()["valid"] is False
    assert old_validation.json()["status"] == "REVOKED"

    reissued = await client.post(
        f"/api/v1/certificates/{first['id']}/reissue",
        json={"reason": "Dados revisados e aprovados"},
        headers=admin_headers,
    )
    assert reissued.status_code == 201, reissued.text
    second = reissued.json()
    assert second["status"] == "ACTIVE"
    assert second["version"] == 2
    assert second["supersedes_id"] == first["id"]

    history = await client.get(
        f"/api/v1/certificates/{first['id']}/history",
        headers=admin_headers,
    )
    assert history.status_code == 200
    assert any(event["event_type"] == "REVOKED" for event in history.json())

    immutable = await client.delete(f"/api/v1/certificates/{second['id']}", headers=admin_headers)
    assert immutable.status_code == 409


@pytest.mark.asyncio
async def test_financial_review_workflow_and_corporate_receivable(client, admin_headers):
    company = await _create_company(client, admin_headers)
    receivable = await client.post(
        "/api/v1/financial/corporate-payments",
        json={
            "company_id": company["id"],
            "amount": 2500.0,
            "method": "PIX",
            "provider": "ASAAS",
            "reference": "NF-OPS-001",
        },
        headers=admin_headers,
    )
    assert receivable.status_code == 201, receivable.text
    payment_id = receivable.json()["id"]
    assert receivable.json()["company_id"] == company["id"]

    review = await client.post(
        f"/api/v1/financial/payments/{payment_id}/review",
        json={"reason": "Conferência manual do recebimento corporativo", "priority": "HIGH"},
        headers=admin_headers,
    )
    assert review.status_code == 200, review.text
    review_id = review.json()["id"]
    assert review.json()["status"] == "OPEN"
    assert review.json()["priority"] == "HIGH"

    claimed = await client.post(
        f"/api/v1/financial/reviews/{review_id}/claim",
        json={"priority": "HIGH"},
        headers=admin_headers,
    )
    assert claimed.status_code == 200
    assert claimed.json()["status"] == "IN_REVIEW"

    resolved = await client.post(
        f"/api/v1/financial/reviews/{review_id}/resolve",
        json={"action": "MARK_APPROVED", "notes": "Pagamento confirmado no extrato do gateway"},
        headers=admin_headers,
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "RESOLVED"
    assert resolved.json()["payment_status"] == "APROVADO"
    assert resolved.json()["review_required"] is False

    events = await client.get(
        f"/api/v1/financial/reviews/{review_id}/events",
        headers=admin_headers,
    )
    assert events.status_code == 200
    event_types = {event["event_type"] for event in events.json()}
    assert {"OPENED", "CLAIMED", "RESOLVED"}.issubset(event_types)

    company_payments = await client.get(
        f"/api/v1/financial/corporate-payments/{company['id']}",
        headers=admin_headers,
    )
    assert company_payments.status_code == 200
    assert any(item["id"] == payment_id for item in company_payments.json())

    summary = await client.get("/api/v1/financial/summary", headers=admin_headers)
    assert summary.status_code == 200
    assert summary.json()["corporate_payments"] >= 1
    assert summary.json()["approved_total"] >= 2500.0


@pytest.mark.asyncio
async def test_operations_dashboard_exposes_new_queues_and_kpis(client, admin_headers):
    stats = await client.get("/api/v1/dashboard/stats", headers=admin_headers)
    assert stats.status_code == 200
    for key in (
        "totalStudents",
        "activeClasses",
        "pendingEnrollments",
        "monthlyRevenue",
        "totalCompanies",
        "corporateEnrollments",
        "completionRate",
        "activeCertificates",
        "expiringCertificates30d",
        "openFinancialReviews",
        "newCorporateRequests",
    ):
        assert key in stats.json()

    operations = await client.get("/api/v1/dashboard/operations", headers=admin_headers)
    assert operations.status_code == 200, operations.text
    body = operations.json()
    assert set(body) == {"summary", "payments", "corporate", "queues"}
    assert set(body["queues"]) == {
        "financialReviews",
        "corporateRequests",
        "expiringCertificates",
    }
    assert "seatUtilization" in body["corporate"]
