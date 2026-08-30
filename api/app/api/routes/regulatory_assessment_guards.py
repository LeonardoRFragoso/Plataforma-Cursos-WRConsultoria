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
from app.models.certificate_signing import CertificateSigningProfile
from app.models.compliance import CourseComplianceProfile
from app.models.enrollment import Enrollment
from app.models.training_evidence import RegulatoryCompletionState
from app.models.user import User
from app.schemas.assessment import (
    AssessmentStartResponse,
    CompletionConfirmationRequest,
    CompletionConfirmationResponse,
)
from app.services.certificate_signing_service import enqueue_signing_job
from app.services.certificate_studio_service import StudioCertificateDocumentService
from app.services.training_evidence_service import evaluate_regulatory_state

router = APIRouter(include_in_schema=False)


async def _prepare_trusted_certificate_if_ready(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    enrollment_id: UUID,
    actor_id: UUID,
) -> CompletionConfirmationResponse:
    """Prepare the immutable CERT-* document as soon as the journey permits it.

    Signing itself stays asynchronous and provider-agnostic. If WR has not yet
    configured an enabled signing profile, the document remains safely in
    PENDING_SIGNATURE instead of falling back to an unsigned official PDF.
    """
    evaluation = await evaluate_regulatory_state(
        db,
        tenant_id=tenant_id,
        enrollment_id=enrollment_id,
        persist=True,
    )
    await db.commit()
    if evaluation.state != RegulatoryCompletionState.CERTIFICATE_PENDING_SIGNATURE:
        return CompletionConfirmationResponse(
            confirmed=True,
            certificate_id=None,
            certificate_number=None,
            validation_code=None,
            is_demo=False,
            regulatory_state=evaluation.state,
        )

    prepared = await StudioCertificateDocumentService.prepare_document(
        db,
        tenant_id=tenant_id,
        enrollment_id=enrollment_id,
        actor_id=actor_id,
        reason="student regulatory completion confirmation",
    )

    profile = (
        await db.execute(
            select(CertificateSigningProfile).where(
                CertificateSigningProfile.tenant_id == tenant_id,
                CertificateSigningProfile.enabled.is_(True),
            )
        )
    ).scalar_one_or_none()
    if profile and profile.provider.strip().upper() != "DISABLED":
        try:
            await enqueue_signing_job(
                db,
                tenant_id=tenant_id,
                certificate_id=prepared.certificate.id,
                actor_id=actor_id,
            )
        except ValueError:
            # The document is intentionally kept PENDING_SIGNATURE if the
            # profile is incomplete/expired. Compliance Operations exposes
            # signer readiness and the job can be enqueued after correction.
            pass

    return CompletionConfirmationResponse(
        confirmed=True,
        certificate_id=prepared.certificate.id,
        certificate_number=prepared.certificate.certificate_number,
        validation_code=prepared.certificate.validation_code,
        is_demo=False,
        regulatory_state=RegulatoryCompletionState.CERTIFICATE_PENDING_SIGNATURE,
    )


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
    """Make regulatory confirmation race-safe, idempotent and document-ready."""
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
        result = await legacy_assessments.confirm_completion(
            attempt_id=attempt_id,
            payload=payload,
            db=db,
            current_user=current_user,
        )
        # Explicit demo journeys continue to use the demo certificate path.
        if result.is_demo or result.certificate_id is not None:
            return result
        return await _prepare_trusted_certificate_if_ready(
            db,
            tenant_id=tenant_id,
            enrollment_id=attempt.enrollment_id,
            actor_id=student.user_id,
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

    return await _prepare_trusted_certificate_if_ready(
        db,
        tenant_id=tenant_id,
        enrollment_id=attempt.enrollment_id,
        actor_id=student.user_id,
    )
