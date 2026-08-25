import uuid

import pytest

from tests.test_prelaunch_operations import _create_company, _create_course_and_class


@pytest.mark.asyncio
async def test_trusted_certificate_edge_contracts(client, admin_headers, student_user):
    _course, class_obj = await _create_course_and_class(
        client,
        admin_headers,
        validity_days=30,
    )
    enrollment = await client.post(
        "/api/v1/enrollments/",
        json={
            "student_id": student_user["student_id"],
            "class_id": class_obj["id"],
            "price": 320.0,
            "status": "CONFIRMADA",
        },
        headers=admin_headers,
    )
    assert enrollment.status_code == 201, enrollment.text
    enrollment_id = enrollment.json()["id"]

    incomplete = await client.post(
        "/api/v1/certificates/",
        json={"enrollment_id": enrollment_id},
        headers=admin_headers,
    )
    assert incomplete.status_code == 409

    completed = await client.put(
        f"/api/v1/enrollments/{enrollment_id}",
        json={"status": "CONCLUIDA"},
        headers=admin_headers,
    )
    assert completed.status_code == 200

    issued = await client.post(
        "/api/v1/certificates/",
        json={"enrollment_id": enrollment_id},
        headers=admin_headers,
    )
    assert issued.status_code == 201, issued.text
    first = issued.json()

    duplicate = await client.post(
        "/api/v1/certificates/",
        json={"enrollment_id": enrollment_id},
        headers=admin_headers,
    )
    assert duplicate.status_code == 409

    mine = await client.get(
        "/api/v1/certificates/me",
        headers=student_user["headers"],
    )
    assert mine.status_code == 200
    assert any(item["id"] == first["id"] for item in mine.json())

    revoked = await client.post(
        f"/api/v1/certificates/{first['id']}/revoke",
        json={"reason": "Correção de homologação"},
        headers=admin_headers,
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "REVOKED"

    revoke_again = await client.post(
        f"/api/v1/certificates/{first['id']}/revoke",
        json={"reason": "Repetição idempotente"},
        headers=admin_headers,
    )
    assert revoke_again.status_code == 200
    assert revoke_again.json()["status"] == "REVOKED"

    blocked_download = await client.get(
        f"/api/v1/certificates/{first['id']}/download",
        headers=student_user["headers"],
    )
    assert blocked_download.status_code == 409

    second_response = await client.post(
        f"/api/v1/certificates/{first['id']}/reissue",
        json={"reason": "Primeira reemissão"},
        headers=admin_headers,
    )
    assert second_response.status_code == 201, second_response.text
    second = second_response.json()
    assert second["version"] == 2

    duplicate_reissue = await client.post(
        f"/api/v1/certificates/{first['id']}/reissue",
        json={"reason": "Tentativa duplicada"},
        headers=admin_headers,
    )
    assert duplicate_reissue.status_code == 409

    third_response = await client.post(
        f"/api/v1/certificates/{second['id']}/reissue",
        json={"reason": "Segunda reemissão"},
        headers=admin_headers,
    )
    assert third_response.status_code == 201, third_response.text
    third = third_response.json()
    assert third["version"] == 3

    superseded_revoke = await client.post(
        f"/api/v1/certificates/{second['id']}/revoke",
        json={"reason": "Não pode revogar registro já substituído"},
        headers=admin_headers,
    )
    assert superseded_revoke.status_code == 409

    immutable = await client.delete(
        f"/api/v1/certificates/{third['id']}",
        headers=admin_headers,
    )
    assert immutable.status_code == 409

    fake = uuid.uuid4()
    assert (
        await client.get(f"/api/v1/certificates/{fake}/history", headers=admin_headers)
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/certificates/{fake}/revoke",
            json={"reason": "Ausente"},
            headers=admin_headers,
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/certificates/{fake}/reissue",
            json={"reason": "Ausente"},
            headers=admin_headers,
        )
    ).status_code == 404
    assert (
        await client.get(
            f"/api/v1/certificates/{fake}/download",
            headers=admin_headers,
        )
    ).status_code == 404


@pytest.mark.asyncio
async def test_corporate_operations_error_contracts(client, admin_headers):
    company = await _create_company(client, admin_headers)
    _course, class_obj = await _create_course_and_class(client, admin_headers)

    missing_request = await client.patch(
        f"/api/v1/corporate/requests/{uuid.uuid4()}",
        json={"status": "QUALIFIED"},
        headers=admin_headers,
    )
    assert missing_request.status_code == 404

    lead = await client.post(
        "/api/v1/corporate/requests",
        json={
            "company_name": "Empresa Edge",
            "contact_name": "RH Edge",
            "contact_email": "rh-edge@example.com",
            "employee_count": 5,
        },
    )
    assert lead.status_code == 201
    invalid_status = await client.patch(
        f"/api/v1/corporate/requests/{lead.json()['id']}",
        json={"status": "INVALID"},
        headers=admin_headers,
    )
    assert invalid_status.status_code == 400

    no_identity = await client.post(
        f"/api/v1/corporate/companies/{company['id']}/employees/link",
        json={},
        headers=admin_headers,
    )
    assert no_identity.status_code == 400

    missing_student = await client.post(
        f"/api/v1/corporate/companies/{company['id']}/employees/link",
        json={"student_id": str(uuid.uuid4())},
        headers=admin_headers,
    )
    assert missing_student.status_code == 404

    incomplete_invite = await client.post(
        f"/api/v1/corporate/companies/{company['id']}/invites",
        json={"email": f"missing-{uuid.uuid4().hex[:6]}@example.com"},
        headers=admin_headers,
    )
    assert incomplete_invite.status_code == 400

    excessive_seats = await client.post(
        f"/api/v1/corporate/companies/{company['id']}/seat-allocations",
        json={"class_id": class_obj["id"], "seats_reserved": 31},
        headers=admin_headers,
    )
    assert excessive_seats.status_code == 409

    missing_offboard = await client.post(
        f"/api/v1/corporate/companies/{company['id']}/employees/{uuid.uuid4()}/offboard",
        json={"deactivate_account": True, "cancel_active_corporate_enrollments": True},
        headers=admin_headers,
    )
    assert missing_offboard.status_code == 404

    rejected_bulk = await client.post(
        f"/api/v1/corporate/companies/{company['id']}/bulk-enroll",
        json={"class_id": class_obj["id"], "student_ids": [str(uuid.uuid4())]},
        headers=admin_headers,
    )
    assert rejected_bulk.status_code == 200
    assert rejected_bulk.json()["created"] == 0
    assert rejected_bulk.json()["rejected"] == 1


@pytest.mark.asyncio
async def test_financial_review_error_and_closure_contracts(client, admin_headers):
    missing_company = await client.post(
        "/api/v1/financial/corporate-payments",
        json={
            "company_id": str(uuid.uuid4()),
            "amount": 1000,
            "method": "PIX",
            "provider": "ASAAS",
        },
        headers=admin_headers,
    )
    assert missing_company.status_code == 404

    company = await _create_company(client, admin_headers)
    payment = await client.post(
        "/api/v1/financial/corporate-payments",
        json={
            "company_id": company["id"],
            "amount": 1000,
            "method": "PIX",
            "provider": "ASAAS",
            "reference": "EDGE-001",
        },
        headers=admin_headers,
    )
    assert payment.status_code == 201, payment.text

    review = await client.post(
        f"/api/v1/financial/payments/{payment.json()['id']}/review",
        json={"reason": "Edge review", "priority": "NORMAL"},
        headers=admin_headers,
    )
    assert review.status_code == 200, review.text
    review_id = review.json()["id"]

    invalid_filter = await client.get(
        "/api/v1/financial/reviews?status_filter=INVALID",
        headers=admin_headers,
    )
    assert invalid_filter.status_code == 400

    invalid_action = await client.post(
        f"/api/v1/financial/reviews/{review_id}/resolve",
        json={"action": "INVALID", "notes": "Não permitido"},
        headers=admin_headers,
    )
    assert invalid_action.status_code == 400

    revoke_without_enrollment = await client.post(
        f"/api/v1/financial/reviews/{review_id}/resolve",
        json={"action": "REVOKE_ACCESS", "notes": "Sem matrícula individual"},
        headers=admin_headers,
    )
    assert revoke_without_enrollment.status_code == 409

    claimed = await client.post(
        f"/api/v1/financial/reviews/{review_id}/claim",
        json={},
        headers=admin_headers,
    )
    assert claimed.status_code == 200

    resolved = await client.post(
        f"/api/v1/financial/reviews/{review_id}/resolve",
        json={"action": "MARK_APPROVED", "notes": "Confirmado"},
        headers=admin_headers,
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "RESOLVED"

    closed_claim = await client.post(
        f"/api/v1/financial/reviews/{review_id}/claim",
        json={},
        headers=admin_headers,
    )
    assert closed_claim.status_code == 409

    missing_review = await client.get(
        f"/api/v1/financial/reviews/{uuid.uuid4()}/events",
        headers=admin_headers,
    )
    assert missing_review.status_code == 404

    suspended = await client.put(
        f"/api/v1/companies/{company['id']}",
        json={"status": "SUSPENDED"},
        headers=admin_headers,
    )
    assert suspended.status_code == 200
    inactive_payment = await client.post(
        "/api/v1/financial/corporate-payments",
        json={
            "company_id": company["id"],
            "amount": 500,
            "method": "PIX",
            "provider": "ASAAS",
        },
        headers=admin_headers,
    )
    assert inactive_payment.status_code == 409
