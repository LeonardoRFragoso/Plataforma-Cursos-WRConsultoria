"""Concurrency/idempotency guards for legacy assessment endpoints.

The public paths remain unchanged. These handlers are registered before the
assessment router and delegate to it after acquiring the regulatory locks that
older clients did not need.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes import assessments as legacy_assessments
from app.core.database import get_db
from app.core.security import get_current_tenant_id, get_current_user, verify_password
from app.models.assessment import AssessmentAttempt, StudentSignatureEvidence
from app.models.compliance import CourseComplianceProfile
from app.models.enrollment import Enrollment
from app.models.user import User
from app.schemas.assessment import (
    AssessmentStartResponse,
    CompletionConfirmationRequest,
    CompletionConfirmationResponse,
)
from app.services.training_evidence_service import evaluate_regulatory_state

router = APIRouter(include_in_schema=False)


@router.post(
    "/assessments/courses/{course_id}/start",
    response_model=AssessmentStartResponse,
    status_code=201,
)
async def guarded_start_assessment(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Serialize attempt-number allocation on the active enrollment row."""
    tenant_id = get_current_tenant_id()
    student = await legacy_assessments._load_student(db, tenant_id, current_user)
    enrollment = await legacy_assessments._load_enrollment(
        db,
        student_id=student.id,
        course_id=course_id,
        tenant_id=tenant_id,
    )
    await db.execute(
        select(Enrollment)
        .where(
            Enrollment.id == enrollment.id,
            Enrollment.tenant_id == tenant_id,
        )
        .with_for_update()
    )
    return await legacy_assessments.start_assessment(
        course_id=course_id,
        db=db,
        current_user=current_user,
    )


@router.post(
    "/assessments/attempts/{attempt_id}/confirm",
    response_model=CompletionConfirmationResponse,
)
async def guarded_confirm_completion(
    attempt_id: UUID,
    payload: CompletionConfirmationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Make regulatory confirmation race-safe and idempotent.

    The attempt lock uses the same lock order as the legacy handler. A repeated
    successful confirmation therefore returns the already-established
    regulatory state instead of racing the unique signature-evidence row or
    returning a false conflict.
    """
    tenant_id = get_current_tenant_id()
    student = await legacy_assessments._load_student(db, tenant_id, current_user)
    attempt = (
        await db.execute(
            select(AssessmentAttempt)
            .where(
                AssessmentAttempt.id == attempt_id,
                AssessmentAttempt.tenant_id == tenant_id,
                AssessmentAttempt.student_id == student.id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Assessment attempt not found")

    profile = (
        await db.execute(
            select(CourseComplianceProfile).where(
                CourseComplianceProfile.tenant_id == tenant_id,
                CourseComplianceProfile.course_id == attempt.course_id,
            )
        )
    ).scalar_one_or_none()
    if profile is None:
        return await legacy_assessments.confirm_completion(
            attempt_id=attempt_id,
            payload=payload,
            db=db,
            current_user=current_user,
        )

    evidence = (
        await db.execute(
            select(StudentSignatureEvidence).where(
                StudentSignatureEvidence.tenant_id == tenant_id,
                StudentSignatureEvidence.enrollment_id == attempt.enrollment_id,
                StudentSignatureEvidence.student_id == student.id,
            )
        )
    ).scalar_one_or_none()
    if evidence is None:
        return await legacy_assessments.confirm_completion(
            attempt_id=attempt_id,
            payload=payload,
            db=db,
            current_user=current_user,
        )

    if not payload.declaration_accepted:
        raise HTTPException(status_code=422, detail="Completion declaration must be accepted")
    user = (
        await db.execute(
            select(User).where(
                User.id == student.user_id,
                User.tenant_id == tenant_id,
                User.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid password confirmation")

    evaluation = await evaluate_regulatory_state(
        db,
        tenant_id=tenant_id,
        enrollment_id=attempt.enrollment_id,
        persist=True,
    )
    await db.commit()
    return CompletionConfirmationResponse(
        confirmed=True,
        certificate_id=None,
        certificate_number=None,
        validation_code=None,
        is_demo=False,
        regulatory_state=evaluation.state,
    )