from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import utc_now
from app.models.assessment import AssessmentAttempt, StudentSignatureEvidence
from app.models.certificate import Certificate
from app.models.class_model import Class
from app.models.compliance import ComplianceStatus, CourseComplianceProfile
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.lesson import Lesson, LessonProgress
from app.models.training_evidence import (
    EnrollmentComplianceProgress,
    PracticalResult,
    PracticalTrainingRecord,
    RegulatoryCompletionState,
    TrainingAccessEvent,
    TrainingEventType,
)


@dataclass
class RegulatoryEvaluation:
    enrollment_id: UUID
    student_id: UUID
    course_id: UUID
    regulatory: bool
    state: str
    blockers: list[str]
    last_evaluated_at: datetime


def _has_course_profile_divergence(course: Course, profile: CourseComplianceProfile) -> bool:
    """Detect divergence between Course table fields and the compliance profile.

    Returns True if:
    - Course.modality != profile.delivery_mode, OR
    - profile.normative_minimum_minutes is set and
      Course.carga_horaria * 60 < profile.normative_minimum_minutes

    This divergence occurs when a regulatory Course field alignment was
    blocked by historical records (MANUAL_REVIEW_REQUIRED). The readiness
    gate must block official certificate issuance until it is resolved.
    """
    # Modality divergence
    course_modality = course.modality.value if hasattr(course.modality, "value") else str(course.modality)
    if course_modality != profile.delivery_mode:
        return True

    # Workload divergence: course carga_horaria below normative minimum
    if profile.normative_minimum_minutes is not None and course.carga_horaria is not None:
        course_minutes = int(course.carga_horaria * 60)
        if course_minutes < profile.normative_minimum_minutes:
            return True

    return False


async def find_active_enrollment(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    student_id: UUID,
    course_id: UUID,
) -> Enrollment | None:
    return (
        await db.execute(
            select(Enrollment)
            .join(Class, Enrollment.class_id == Class.id)
            .where(
                Enrollment.tenant_id == tenant_id,
                Enrollment.student_id == student_id,
                Class.tenant_id == tenant_id,
                Class.course_id == course_id,
                Enrollment.status.in_([EnrollmentStatus.CONFIRMADA, EnrollmentStatus.CONCLUIDA]),
            )
            .order_by(
                (Enrollment.status == EnrollmentStatus.CONFIRMADA).desc(),
                Enrollment.enrollment_date.desc(),
            )
            .limit(1)
        )
    ).scalar_one_or_none()


async def record_training_event(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    enrollment_id: UUID,
    student_id: UUID,
    course_id: UUID,
    event_type: str,
    actor_user_id: UUID | None = None,
    lesson_id: UUID | None = None,
    session_id: UUID | None = None,
    client_fingerprint: str | None = None,
    details: dict | None = None,
) -> TrainingAccessEvent:
    event = TrainingAccessEvent(
        tenant_id=tenant_id,
        enrollment_id=enrollment_id,
        student_id=student_id,
        course_id=course_id,
        lesson_id=lesson_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        session_id=session_id,
        client_fingerprint=client_fingerprint,
        details=details or {},
    )
    db.add(event)
    await db.flush()
    return event


async def _persist_evaluation(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    enrollment: Enrollment,
    course_id: UUID,
    state: str,
    blockers: list[str],
) -> EnrollmentComplianceProgress:
    """Persist current state after the enrollment row has been locked.

    ``evaluate_regulatory_state`` takes a row-level lock on the Enrollment
    before entering this function. That single lock serializes concurrent
    evaluations for the same enrollment and makes first-row creation safe
    without an application-level mutex.
    """
    now = utc_now()
    progress = (
        await db.execute(
            select(EnrollmentComplianceProgress).where(
                EnrollmentComplianceProgress.tenant_id == tenant_id,
                EnrollmentComplianceProgress.enrollment_id == enrollment.id,
            )
        )
    ).scalar_one_or_none()
    previous_state = progress.state if progress else None
    if progress is None:
        progress = EnrollmentComplianceProgress(
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            student_id=enrollment.student_id,
            course_id=course_id,
            state=state,
            blockers=blockers,
            state_updated_at=now,
            last_evaluated_at=now,
        )
        db.add(progress)
        await db.flush()
    else:
        progress.blockers = blockers
        progress.last_evaluated_at = now
        if progress.state != state:
            progress.state = state
            progress.state_updated_at = now

    if previous_state != state:
        await record_training_event(
            db,
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            student_id=enrollment.student_id,
            course_id=course_id,
            event_type=TrainingEventType.STATE_TRANSITION,
            details={"from": previous_state, "to": state, "blockers": blockers},
        )
    return progress


async def evaluate_regulatory_state(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    enrollment_id: UUID,
    persist: bool = True,
) -> RegulatoryEvaluation:
    stmt = (
        select(Enrollment, Class, Course)
        .join(Class, Enrollment.class_id == Class.id)
        .join(Course, Class.course_id == Course.id)
        .where(
            Enrollment.id == enrollment_id,
            Enrollment.tenant_id == tenant_id,
            Class.tenant_id == tenant_id,
            Course.tenant_id == tenant_id,
        )
    )
    if persist:
        # All state mutations for an enrollment serialize on this row. Using
        # OF Enrollment avoids unnecessarily locking Course/Class rows.
        stmt = stmt.with_for_update(of=Enrollment)
    row = (await db.execute(stmt)).first()
    if not row:
        raise LookupError("Enrollment not found")
    enrollment, class_obj, course = row
    now = utc_now()

    profile = (
        await db.execute(
            select(CourseComplianceProfile).where(
                CourseComplianceProfile.tenant_id == tenant_id,
                CourseComplianceProfile.course_id == course.id,
            )
        )
    ).scalar_one_or_none()
    if profile is None:
        return RegulatoryEvaluation(
            enrollment_id=enrollment.id,
            student_id=enrollment.student_id,
            course_id=course.id,
            regulatory=False,
            state=RegulatoryCompletionState.NOT_REGULATORY,
            blockers=[],
            last_evaluated_at=now,
        )

    blockers: list[str] = []
    state = RegulatoryCompletionState.ENROLLED

    if enrollment.status == EnrollmentStatus.CANCELADA:
        state = RegulatoryCompletionState.CANCELLED
    elif profile.status != ComplianceStatus.COMPLIANCE_READY:
        state = RegulatoryCompletionState.COMPLIANCE_REVIEW_REQUIRED
        blockers.append("Course compliance profile requires review")
    elif _has_course_profile_divergence(course, profile):
        # Course table fields (modality, carga_horaria) diverge from the
        # regulatory compliance profile. This happens when a Course field
        # alignment was blocked by historical records (MANUAL_REVIEW_REQUIRED).
        # Block official certificate issuance until the divergence is resolved.
        state = RegulatoryCompletionState.COMPLIANCE_REVIEW_REQUIRED
        blockers.append("COURSE_FIELD_HISTORY_CONFLICT: Course fields diverge from compliance profile")
    elif profile.next_compliance_review_at and profile.next_compliance_review_at <= now:
        state = RegulatoryCompletionState.COMPLIANCE_REVIEW_REQUIRED
        blockers.append("Course compliance review has expired")
    elif not class_obj.pedagogical_project_version_id:
        state = RegulatoryCompletionState.COMPLIANCE_REVIEW_REQUIRED
        blockers.append("Class has no pinned pedagogical project version")
    else:
        required_total = int(
            await db.scalar(
                select(func.count(Lesson.id)).where(
                    Lesson.tenant_id == tenant_id,
                    Lesson.course_id == course.id,
                    Lesson.is_required.is_(True),
                )
            )
            or 0
        )
        progress_count = int(
            await db.scalar(
                select(func.count(LessonProgress.id))
                .join(Lesson, LessonProgress.lesson_id == Lesson.id)
                .where(
                    LessonProgress.tenant_id == tenant_id,
                    LessonProgress.student_id == enrollment.student_id,
                    Lesson.tenant_id == tenant_id,
                    Lesson.course_id == course.id,
                )
            )
            or 0
        )
        completed_required = int(
            await db.scalar(
                select(func.count(LessonProgress.id))
                .join(Lesson, LessonProgress.lesson_id == Lesson.id)
                .where(
                    LessonProgress.tenant_id == tenant_id,
                    LessonProgress.student_id == enrollment.student_id,
                    Lesson.tenant_id == tenant_id,
                    Lesson.course_id == course.id,
                    Lesson.is_required.is_(True),
                    LessonProgress.completed.is_(True),
                )
            )
            or 0
        )

        if required_total == 0:
            state = RegulatoryCompletionState.IN_PROGRESS
            blockers.append("Required training content is not configured")
        elif completed_required < required_total:
            state = (
                RegulatoryCompletionState.IN_PROGRESS
                if progress_count > 0
                else RegulatoryCompletionState.ENROLLED
            )
            blockers.append(f"Required lessons incomplete ({completed_required}/{required_total})")
        else:
            state = RegulatoryCompletionState.CONTENT_COMPLETED

            if profile.requires_final_assessment:
                attempts = list(
                    (
                        await db.execute(
                            select(AssessmentAttempt)
                            .where(
                                AssessmentAttempt.tenant_id == tenant_id,
                                AssessmentAttempt.enrollment_id == enrollment.id,
                                AssessmentAttempt.completed_at.is_not(None),
                            )
                            .order_by(AssessmentAttempt.attempt_number.desc())
                        )
                    ).scalars().all()
                )
                passed_attempt = next((item for item in attempts if item.passed), None)
                if passed_attempt is None:
                    if attempts:
                        state = RegulatoryCompletionState.ASSESSMENT_UNSATISFACTORY
                        blockers.append("Final assessment has no satisfactory attempt")
                    else:
                        state = RegulatoryCompletionState.ASSESSMENT_PENDING
                        blockers.append("Final assessment is pending")
                else:
                    state = RegulatoryCompletionState.ASSESSMENT_SATISFACTORY

            if state in {
                RegulatoryCompletionState.CONTENT_COMPLETED,
                RegulatoryCompletionState.ASSESSMENT_SATISFACTORY,
            } and profile.requires_practical_component:
                # Corrections are append-only and can reference an older
                # performed_at. The latest *recorded* fact must therefore win.
                latest_practical = (
                    await db.execute(
                        select(PracticalTrainingRecord)
                        .where(
                            PracticalTrainingRecord.tenant_id == tenant_id,
                            PracticalTrainingRecord.enrollment_id == enrollment.id,
                        )
                        .order_by(
                            PracticalTrainingRecord.created_at.desc(),
                            PracticalTrainingRecord.performed_at.desc(),
                        )
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if not latest_practical or latest_practical.result != PracticalResult.SATISFACTORY:
                    state = RegulatoryCompletionState.PRACTICAL_COMPONENT_PENDING
                    blockers.append("Practical component has no current satisfactory record")

            if state in {
                RegulatoryCompletionState.CONTENT_COMPLETED,
                RegulatoryCompletionState.ASSESSMENT_SATISFACTORY,
            }:
                evidence = (
                    await db.execute(
                        select(StudentSignatureEvidence).where(
                            StudentSignatureEvidence.tenant_id == tenant_id,
                            StudentSignatureEvidence.enrollment_id == enrollment.id,
                        )
                    )
                ).scalar_one_or_none()
                if evidence is None:
                    state = RegulatoryCompletionState.STUDENT_CONFIRMATION_PENDING
                    blockers.append("Student completion confirmation is pending")
                else:
                    certificate = (
                        await db.execute(
                            select(Certificate).where(
                                Certificate.tenant_id == tenant_id,
                                Certificate.enrollment_id == enrollment.id,
                                Certificate.status == "ACTIVE",
                                ~Certificate.certificate_number.like("DEMO-%"),
                            )
                        )
                    ).scalar_one_or_none()
                    state = (
                        RegulatoryCompletionState.CERTIFIED
                        if certificate
                        else RegulatoryCompletionState.CERTIFICATE_PENDING_SIGNATURE
                    )
                    if certificate is None:
                        blockers.append("Trusted certificate signature pipeline is pending")

    if persist:
        progress = await _persist_evaluation(
            db,
            tenant_id=tenant_id,
            enrollment=enrollment,
            course_id=course.id,
            state=state,
            blockers=blockers,
        )
        evaluated_at = progress.last_evaluated_at
    else:
        evaluated_at = now

    return RegulatoryEvaluation(
        enrollment_id=enrollment.id,
        student_id=enrollment.student_id,
        course_id=course.id,
        regulatory=True,
        state=state,
        blockers=blockers,
        last_evaluated_at=evaluated_at,
    )
