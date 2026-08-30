import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.class_model import Class
from app.models.compliance import ComplianceStatus, CourseComplianceProfile
from app.services.assessment_service import QUESTION_BANKS
from tests.test_training_evidence_runtime import _complete_lesson, _create_course


async def _pass_assessment(client, fixture):
    await _complete_lesson(client, fixture)
    started = await client.post(
        f"/api/v1/assessments/courses/{fixture['course']['id']}/start",
        headers=fixture["student_headers"],
    )
    assert started.status_code == 201, started.text
    answers = {
        item["id"]: item["correct"]
        for item in QUESTION_BANKS[fixture["course"]["code"]]
    }
    submitted = await client.post(
        f"/api/v1/assessments/attempts/{started.json()['attempt_id']}/submit",
        json={"answers": answers},
        headers=fixture["student_headers"],
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["passed"] is True
    return started.json()["attempt_id"]


async def _mark_profile_review_required(fixture, *, demo_class: bool):
    async with AsyncSessionLocal() as db:
        profile = (
            await db.execute(
                select(CourseComplianceProfile).where(
                    CourseComplianceProfile.id == fixture["course"]["id"]
                )
            )
        ).scalar_one_or_none()
        if profile is None:
            profile = (
                await db.execute(
                    select(CourseComplianceProfile).where(
                        CourseComplianceProfile.course_id == fixture["course"]["id"]
                    )
                )
            ).scalar_one()
        profile.status = ComplianceStatus.REVIEW_REQUIRED
        if demo_class:
            cls = (
                await db.execute(select(Class).where(Class.id == fixture["class"]["id"]))
            ).scalar_one()
            cls.location = "DEMO-EAD-ASSESSMENT"
        await db.commit()


@pytest.mark.asyncio
async def test_confirmed_demo_enrollment_can_issue_demo_certificate_while_profile_is_under_review(
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
    attempt_id = await _pass_assessment(client, fixture)
    await _mark_profile_review_required(fixture, demo_class=True)

    confirmed = await client.post(
        f"/api/v1/assessments/attempts/{attempt_id}/confirm",
        json={
            "password": fixture["password"],
            "declaration_accepted": True,
        },
        headers=fixture["student_headers"],
    )

    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert body["confirmed"] is True
    assert body["is_demo"] is True
    assert body["certificate_id"] is not None
    assert body["certificate_number"].startswith("DEMO-")
    assert body["validation_code"]
    assert body["regulatory_state"] is None


@pytest.mark.asyncio
async def test_non_demo_enrollment_remains_blocked_when_profile_is_under_review(
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
    attempt_id = await _pass_assessment(client, fixture)
    await _mark_profile_review_required(fixture, demo_class=False)

    blocked = await client.post(
        f"/api/v1/assessments/attempts/{attempt_id}/confirm",
        json={
            "password": fixture["password"],
            "declaration_accepted": True,
        },
        headers=fixture["student_headers"],
    )

    assert blocked.status_code == 409, blocked.text
    detail = blocked.json()["detail"]
    assert detail["state"] == "COMPLIANCE_REVIEW_REQUIRED"
    assert "Course compliance profile requires review" in detail["blockers"]
