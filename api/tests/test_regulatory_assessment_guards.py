import pytest

from app.services.assessment_service import QUESTION_BANKS
from tests.test_training_evidence_runtime import _complete_lesson, _create_course


@pytest.mark.asyncio
async def test_legacy_assessment_confirmation_is_idempotent_for_regulatory_course(
    client,
    admin_headers,
):
    fixture = await _create_course(
        client,
        admin_headers,
        code="NR-06-F",
        requires_assessment=True,
        requires_practical=False,
    )
    await _complete_lesson(client, fixture)

    started = await client.post(
        f"/api/v1/assessments/courses/{fixture['course']['id']}/start",
        headers=fixture["student_headers"],
    )
    assert started.status_code == 201, started.text

    answers = {
        item["id"]: item["correct"]
        for item in QUESTION_BANKS["NR-06-F"]
    }
    submitted = await client.post(
        f"/api/v1/assessments/attempts/{started.json()['attempt_id']}/submit",
        json={"answers": answers},
        headers=fixture["student_headers"],
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["passed"] is True

    payload = {
        "password": fixture["password"],
        "declaration_accepted": True,
    }
    first = await client.post(
        f"/api/v1/assessments/attempts/{started.json()['attempt_id']}/confirm",
        json=payload,
        headers=fixture["student_headers"],
    )
    assert first.status_code == 200, first.text
    assert first.json()["regulatory_state"] == "CERTIFICATE_PENDING_SIGNATURE"
    assert first.json()["certificate_id"] is not None
    assert first.json()["certificate_number"].startswith("CERT-")
    assert first.json()["validation_code"]
    assert first.json()["is_demo"] is False

    repeated = await client.post(
        f"/api/v1/assessments/attempts/{started.json()['attempt_id']}/confirm",
        json=payload,
        headers=fixture["student_headers"],
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["regulatory_state"] == "CERTIFICATE_PENDING_SIGNATURE"
    assert repeated.json()["certificate_id"] == first.json()["certificate_id"]
    assert repeated.json()["certificate_number"] == first.json()["certificate_number"]
    assert repeated.json()["validation_code"] == first.json()["validation_code"]
