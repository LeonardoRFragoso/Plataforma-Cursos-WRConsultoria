from __future__ import annotations

import hashlib
import hmac
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.proxy import get_client_ip
from app.core.security import (
    get_current_admin,
    get_current_tenant_id,
    get_current_user,
    verify_password,
)
from app.core.utils import utc_now
from app.models.assessment import AssessmentAttempt, StudentSignatureEvidence
from app.models.class_model import Class
from app.models.compliance import (
    CourseComplianceProfile,
    CourseTrainingProfessional,
    ProfessionalAssignmentRole,
    TrainingProfessional,
)
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.student import Student
from app.models.training_evidence import (
    PracticalTrainingRecord,
    RegulatoryCompletionState,
    TrainingAccessEvent,
    TrainingEventType,
)
from app.models.user import User
from app.schemas.training_evidence import (
    PracticalTrainingRecordCreate,
    PracticalTrainingRecordResponse,
    RegulatoryCompletionConfirmRequest,
    RegulatoryCompletionConfirmResponse,
    RegulatoryStateResponse,
    TrainingAccessEventResponse,
    TrainingEvidenceExportResponse,
    TrainingSessionEndResponse,
    TrainingSessionResponse,
)
from app.services.training_evidence_service import (
    evaluate_regulatory_state,
    record_training_event,
)

router = APIRouter()


def _fingerprint(request: Request) -> str | None:
    """Return a non-reversible client fingerprint without storing raw IP/UA."""
    ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")[:512]
    if not ip and not user_agent:
        return None
    key = settings.SECRET_KEY.encode("utf-8")
    payload = f"{ip or ''}|{user_agent}".encode("utf-8")
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


async def _enrollment_context(db: AsyncSession, tenant_id: UUID, enrollment_id: UUID):
    row = (
        await db.execute(
            select(Enrollment, Student, Class, Course)
            .join(Student, Enrollment.student_id == Student.id)
            .join(Class, Enrollment.class_id == Class.id)
            .join(Course, Class.course_id == Course.id)
            .where(
                Enrollment.id == enrollment_id,
                Enrollment.tenant_id == tenant_id,
                Student.tenant_id == tenant_id,
                Class.tenant_id == tenant_id,
                Course.tenant_id == tenant_id,
            )
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    return row


def _authorize_student_or_admin(student: Student, current_user: dict) -> None:
    if current_user.get("role") in {"admin", "super_admin"}:
        return
    if str(student.user_id) == current_user.get("user_id"):
        return
    raise HTTPException(status_code=403, detail="Cannot access this training evidence")


def _require_student_owner(student: Student, current_user: dict) -> None:
    if current_user.get("role") != "student" or str(student.user_id) != current_user.get("user_id"):
        raise HTTPException(status_code=403, detail="Student ownership required")


def _state_response(evaluation) -> RegulatoryStateResponse:
    return RegulatoryStateResponse(
        enrollment_id=evaluation.enrollment_id,
        student_id=evaluation.student_id,
        course_id=evaluation.course_id,
        regulatory=evaluation.regulatory,
        state=evaluation.state,
        blockers=evaluation.blockers,
        last_evaluated_at=evaluation.last_evaluated_at,
    )


async def _require_regulatory(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    enrollment_id: UUID,
    persist: bool = False,
):
    evaluation = await evaluate_regulatory_state(
        db,
        tenant_id=tenant_id,
        enrollment_id=enrollment_id,
        persist=persist,
    )
    if not evaluation.regulatory:
        raise HTTPException(
            status_code=409,
            detail="Regulatory training evidence is not enabled for this enrollment",
        )
    return evaluation


@router.get(
    "/enrollments/{enrollment_id}/state",
    response_model=RegulatoryStateResponse,
)
async def get_regulatory_state(
    enrollment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    _enrollment, student, _class, _course = await _enrollment_context(db, tenant_id, enrollment_id)
    _authorize_student_or_admin(student, current_user)
    evaluation = await evaluate_regulatory_state(
        db,
        tenant_id=tenant_id,
        enrollment_id=enrollment_id,
    )
    await db.commit()
    return _state_response(evaluation)


@router.post(
    "/enrollments/{enrollment_id}/sessions/start",
    response_model=TrainingSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_training_session(
    enrollment_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    enrollment, student, _class, course = await _enrollment_context(db, tenant_id, enrollment_id)
    _require_student_owner(student, current_user)
    await _require_regulatory(
        db,
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
        persist=False,
    )

    session_id = uuid4()
    event = await record_training_event(
        db,
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
        student_id=student.id,
        course_id=course.id,
        actor_user_id=student.user_id,
        event_type=TrainingEventType.SESSION_STARTED,
        session_id=session_id,
        client_fingerprint=_fingerprint(request),
    )
    await evaluate_regulatory_state(
        db,
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
    )
    await db.commit()
    return TrainingSessionResponse(
        session_id=session_id,
        enrollment_id=enrollment.id,
        course_id=course.id,
        started_at=event.occurred_at,
    )


@router.post(
    "/enrollments/{enrollment_id}/sessions/{session_id}/end",
    response_model=TrainingSessionEndResponse,
)
async def end_training_session(
    enrollment_id: UUID,
    session_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    enrollment, student, _class, course = await _enrollment_context(db, tenant_id, enrollment_id)
    _require_student_owner(student, current_user)
    await _require_regulatory(
        db,
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
        persist=False,
    )

    started = (
        await db.execute(
            select(TrainingAccessEvent).where(
                TrainingAccessEvent.tenant_id == tenant_id,
                TrainingAccessEvent.enrollment_id == enrollment.id,
                TrainingAccessEvent.student_id == student.id,
                TrainingAccessEvent.session_id == session_id,
                TrainingAccessEvent.event_type == TrainingEventType.SESSION_STARTED,
            )
        )
    ).scalar_one_or_none()
    if not started:
        raise HTTPException(status_code=404, detail="Training session not found")
    ended = (
        await db.execute(
            select(TrainingAccessEvent.id).where(
                TrainingAccessEvent.tenant_id == tenant_id,
                TrainingAccessEvent.enrollment_id == enrollment.id,
                TrainingAccessEvent.session_id == session_id,
                TrainingAccessEvent.event_type == TrainingEventType.SESSION_ENDED,
            )
        )
    ).scalar_one_or_none()
    if ended:
        raise HTTPException(status_code=409, detail="Training session already ended")

    event = await record_training_event(
        db,
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
        student_id=student.id,
        course_id=course.id,
        actor_user_id=student.user_id,
        event_type=TrainingEventType.SESSION_ENDED,
        session_id=session_id,
        client_fingerprint=_fingerprint(request),
    )
    await db.commit()
    return TrainingSessionEndResponse(session_id=session_id, ended_at=event.occurred_at)


@router.post(
    "/enrollments/{enrollment_id}/confirm",
    response_model=RegulatoryCompletionConfirmResponse,
)
async def confirm_regulatory_completion(
    enrollment_id: UUID,
    payload: RegulatoryCompletionConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Authenticated completion confirmation for all regulatory courses.

    This route supports courses both with and without a final assessment. It
    never issues a certificate directly; a successful confirmation advances
    the state to CERTIFICATE_PENDING_SIGNATURE for the signed-document phase.
    """
    if not payload.declaration_accepted:
        raise HTTPException(status_code=422, detail="Completion declaration must be accepted")

    tenant_id = get_current_tenant_id()
    enrollment, student, _class, course = await _enrollment_context(db, tenant_id, enrollment_id)
    _require_student_owner(student, current_user)
    evaluation = await _require_regulatory(
        db,
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
        persist=True,
    )

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

    existing = (
        await db.execute(
            select(StudentSignatureEvidence).where(
                StudentSignatureEvidence.tenant_id == tenant_id,
                StudentSignatureEvidence.enrollment_id == enrollment.id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        if evaluation.state not in {
            RegulatoryCompletionState.CERTIFICATE_PENDING_SIGNATURE,
            RegulatoryCompletionState.CERTIFIED,
        }:
            await db.commit()
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Completion was already confirmed but current regulatory facts require review",
                    "state": evaluation.state,
                    "blockers": evaluation.blockers,
                },
            )
        await db.commit()
        return RegulatoryCompletionConfirmResponse(
            confirmed=True,
            state=_state_response(evaluation),
        )

    if evaluation.state != RegulatoryCompletionState.STUDENT_CONFIRMATION_PENDING:
        await db.commit()
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Regulatory completion requirements are not satisfied",
                "state": evaluation.state,
                "blockers": evaluation.blockers,
            },
        )

    profile = (
        await db.execute(
            select(CourseComplianceProfile).where(
                CourseComplianceProfile.tenant_id == tenant_id,
                CourseComplianceProfile.course_id == course.id,
            )
        )
    ).scalar_one()
    assessment_attempt_id = None
    if profile.requires_final_assessment:
        passed_attempt = (
            await db.execute(
                select(AssessmentAttempt)
                .where(
                    AssessmentAttempt.tenant_id == tenant_id,
                    AssessmentAttempt.enrollment_id == enrollment.id,
                    AssessmentAttempt.student_id == student.id,
                    AssessmentAttempt.passed.is_(True),
                    AssessmentAttempt.completed_at.is_not(None),
                )
                .order_by(AssessmentAttempt.attempt_number.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if not passed_attempt:
            raise HTTPException(status_code=409, detail="Passing assessment evidence is missing")
        assessment_attempt_id = passed_attempt.id

    evidence = StudentSignatureEvidence(
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
        student_id=student.id,
        course_id=course.id,
        assessment_attempt_id=assessment_attempt_id,
        declaration_version="regulatory-completion-v1",
        auth_method="PASSWORD_REAUTH",
    )
    db.add(evidence)
    enrollment.status = EnrollmentStatus.CONCLUIDA
    await db.flush()
    await record_training_event(
        db,
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
        student_id=student.id,
        course_id=course.id,
        actor_user_id=user.id,
        event_type=TrainingEventType.STUDENT_CONFIRMATION,
        details={
            "assessment_attempt_id": str(assessment_attempt_id) if assessment_attempt_id else None,
            "declaration_version": evidence.declaration_version,
            "auth_method": evidence.auth_method,
        },
    )
    evaluation = await evaluate_regulatory_state(
        db,
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
    )
    await db.commit()
    return RegulatoryCompletionConfirmResponse(
        confirmed=True,
        state=_state_response(evaluation),
    )


@router.post(
    "/enrollments/{enrollment_id}/practical-records",
    response_model=PracticalTrainingRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_practical_component(
    enrollment_id: UUID,
    payload: PracticalTrainingRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    enrollment, student, _class, course = await _enrollment_context(db, tenant_id, enrollment_id)
    profile = (
        await db.execute(
            select(CourseComplianceProfile).where(
                CourseComplianceProfile.tenant_id == tenant_id,
                CourseComplianceProfile.course_id == course.id,
            )
        )
    ).scalar_one_or_none()
    if not profile or not profile.requires_practical_component:
        raise HTTPException(status_code=409, detail="This enrollment does not require a practical component")

    instructor = (
        await db.execute(
            select(TrainingProfessional).where(
                TrainingProfessional.id == payload.instructor_id,
                TrainingProfessional.tenant_id == tenant_id,
                TrainingProfessional.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not instructor:
        raise HTTPException(status_code=404, detail="Active training professional not found")
    assignment = (
        await db.execute(
            select(CourseTrainingProfessional.id).where(
                CourseTrainingProfessional.tenant_id == tenant_id,
                CourseTrainingProfessional.course_id == course.id,
                CourseTrainingProfessional.professional_id == instructor.id,
                CourseTrainingProfessional.role.in_(
                    [
                        ProfessionalAssignmentRole.INSTRUCTOR,
                        ProfessionalAssignmentRole.TECHNICAL_RESPONSIBLE,
                    ]
                ),
            )
        )
    ).scalar_one_or_none()
    if not assignment:
        raise HTTPException(
            status_code=409,
            detail="Professional must be assigned to the course before recording practice",
        )

    if payload.supersedes_id:
        superseded = (
            await db.execute(
                select(PracticalTrainingRecord).where(
                    PracticalTrainingRecord.id == payload.supersedes_id,
                    PracticalTrainingRecord.tenant_id == tenant_id,
                    PracticalTrainingRecord.enrollment_id == enrollment.id,
                )
            )
        ).scalar_one_or_none()
        if not superseded:
            raise HTTPException(status_code=404, detail="Superseded practical record not found")

    record = PracticalTrainingRecord(
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
        student_id=student.id,
        course_id=course.id,
        instructor_id=instructor.id,
        supersedes_id=payload.supersedes_id,
        result=payload.result,
        performed_at=payload.performed_at,
        duration_minutes=payload.duration_minutes,
        location=payload.location,
        notes=payload.notes.strip() if payload.notes else None,
        instructor_snapshot={
            "id": str(instructor.id),
            "name": instructor.full_name,
            "qualification": instructor.qualification,
            "professional_registration": instructor.professional_registration,
            "council": instructor.council,
            "registration_state": instructor.registration_state,
        },
        recorded_by=UUID(current_user["user_id"]),
    )
    db.add(record)
    await db.flush()
    await record_training_event(
        db,
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
        student_id=student.id,
        course_id=course.id,
        actor_user_id=UUID(current_user["user_id"]),
        event_type=TrainingEventType.PRACTICAL_COMPONENT_RECORDED,
        details={
            "practical_record_id": str(record.id),
            "result": record.result,
            "supersedes_id": str(record.supersedes_id) if record.supersedes_id else None,
        },
    )
    await evaluate_regulatory_state(
        db,
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
    )
    await db.commit()
    await db.refresh(record)
    return record


@router.get(
    "/enrollments/{enrollment_id}/practical-records",
    response_model=list[PracticalTrainingRecordResponse],
)
async def list_practical_records(
    enrollment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    _enrollment, student, _class, _course = await _enrollment_context(db, tenant_id, enrollment_id)
    _authorize_student_or_admin(student, current_user)
    return (
        await db.execute(
            select(PracticalTrainingRecord)
            .where(
                PracticalTrainingRecord.tenant_id == tenant_id,
                PracticalTrainingRecord.enrollment_id == enrollment_id,
            )
            .order_by(
                PracticalTrainingRecord.created_at.desc(),
                PracticalTrainingRecord.performed_at.desc(),
            )
        )
    ).scalars().all()


@router.get(
    "/enrollments/{enrollment_id}/export",
    response_model=TrainingEvidenceExportResponse,
)
async def export_training_evidence(
    enrollment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    enrollment, student, _class, course = await _enrollment_context(db, tenant_id, enrollment_id)
    evaluation = await _require_regulatory(
        db,
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
        persist=True,
    )
    await record_training_event(
        db,
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
        student_id=student.id,
        course_id=course.id,
        actor_user_id=UUID(current_user["user_id"]),
        event_type=TrainingEventType.EVIDENCE_EXPORTED,
        details={"format": "JSON", "scope": "enrollment"},
    )
    await db.flush()

    practical_records = list(
        (
            await db.execute(
                select(PracticalTrainingRecord)
                .where(
                    PracticalTrainingRecord.tenant_id == tenant_id,
                    PracticalTrainingRecord.enrollment_id == enrollment.id,
                )
                .order_by(PracticalTrainingRecord.created_at.asc())
            )
        ).scalars().all()
    )
    events = list(
        (
            await db.execute(
                select(TrainingAccessEvent)
                .where(
                    TrainingAccessEvent.tenant_id == tenant_id,
                    TrainingAccessEvent.enrollment_id == enrollment.id,
                )
                .order_by(TrainingAccessEvent.occurred_at.asc(), TrainingAccessEvent.created_at.asc())
            )
        ).scalars().all()
    )
    await db.commit()
    return TrainingEvidenceExportResponse(
        enrollment_id=enrollment.id,
        state=_state_response(evaluation),
        practical_records=[PracticalTrainingRecordResponse.model_validate(item) for item in practical_records],
        events=[TrainingAccessEventResponse.model_validate(item) for item in events],
        exported_at=utc_now(),
    )
