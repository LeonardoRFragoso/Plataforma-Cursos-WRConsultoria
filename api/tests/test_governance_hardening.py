import uuid

import pytest


@pytest.mark.asyncio
async def test_student_privacy_request_lifecycle_and_export(client, student_user, admin_headers):
    student_headers = student_user["headers"]

    created = await client.post(
        "/api/v1/privacy/requests",
        json={
            "request_type": "export",
            "details": "Solicito uma cópia dos meus dados cadastrados.",
        },
        headers=student_headers,
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    assert created.json()["request_type"] == "EXPORT"
    assert created.json()["status"] == "OPEN"

    duplicate = await client.post(
        "/api/v1/privacy/requests",
        json={"request_type": "EXPORT"},
        headers=student_headers,
    )
    assert duplicate.status_code == 409

    mine = await client.get("/api/v1/privacy/requests/me", headers=student_headers)
    assert mine.status_code == 200
    assert any(item["id"] == request_id for item in mine.json())

    exported = await client.get("/api/v1/privacy/me/export", headers=student_headers)
    assert exported.status_code == 200, exported.text
    body = exported.json()
    assert body["account"]["email"] == student_user["email"]
    assert body["student_profile"]["id"] == student_user["student_id"]
    assert "password_hash" not in body["account"]
    assert "access_token" not in str(body).lower()
    assert body["tenant_id"]

    queue = await client.get(
        "/api/v1/privacy/requests?status_filter=OPEN&request_type=EXPORT",
        headers=admin_headers,
    )
    assert queue.status_code == 200
    assert any(item["id"] == request_id for item in queue.json())

    completed = await client.patch(
        f"/api/v1/privacy/requests/{request_id}",
        json={
            "status": "COMPLETED",
            "admin_notes": "Solicitação analisada e atendida sem exclusão automática.",
        },
        headers=admin_headers,
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "COMPLETED"
    assert completed.json()["resolved_by"]
    assert completed.json()["resolved_at"]


@pytest.mark.asyncio
async def test_privacy_request_validation(client, student_user, admin_headers):
    invalid_type = await client.post(
        "/api/v1/privacy/requests",
        json={"request_type": "DELETE_EVERYTHING_NOW"},
        headers=student_user["headers"],
    )
    assert invalid_type.status_code == 400

    invalid_status = await client.get(
        "/api/v1/privacy/requests?status_filter=INVALID",
        headers=admin_headers,
    )
    assert invalid_status.status_code == 400

    missing = await client.patch(
        f"/api/v1/privacy/requests/{uuid.uuid4()}",
        json={"status": "IN_REVIEW"},
        headers=admin_headers,
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_admin_mutation_is_audited_without_payload(client, admin_headers):
    # Any authenticated administrative mutation must create metadata evidence.
    mutation = await client.post(
        "/api/v1/privacy/requests",
        json={
            "request_type": "CORRECTION",
            "details": "audit-sensitive-value-that-must-not-be-stored-in-audit-log",
        },
        headers=admin_headers,
    )
    assert mutation.status_code == 201, mutation.text

    audit = await client.get(
        "/api/v1/governance/audit?method=POST&limit=100",
        headers=admin_headers,
    )
    assert audit.status_code == 200, audit.text
    records = [
        item
        for item in audit.json()
        if item["path"] == "/api/v1/privacy/requests"
    ]
    assert records
    latest = records[0]
    assert latest["method"] == "POST"
    assert latest["status_code"] == 201
    assert latest["actor_id"]
    # Contract is metadata-only; no body/details fields exist in response/schema.
    assert "details" not in latest
    assert "body" not in latest


@pytest.mark.asyncio
async def test_student_cannot_read_administrative_audit(client, student_user):
    response = await client.get(
        "/api/v1/governance/audit",
        headers=student_user["headers"],
    )
    assert response.status_code == 403
