"""Student final-assessment and demo completion routes.

These endpoints provide the authenticated student journey for courses whose
final assessment is configured in ``assessment_service``.  They deliberately
persist lesson progress without invoking the legacy lesson auto-certificate
path; certification happens only after a passing assessment and explicit
password re-authentication/declaration confirmation.
"""

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_tenant_id, get_current_user, verify_password
from app.core.utils import utc_now
from app.models.assessment import AssessmentAttempt, StudentSignatureEvidence
from app.models.certificate import Certificate
from app.models.class_model import Class, ClassStatus
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.lesson import Lesson, LessonContentType, LessonProgress
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.assessment import (
    AssessmentResultResponse,
    AssessmentStartResponse,
    AssessmentStatusResponse,
    CompletionConfirmationRequest,
    CompletionConfirmationResponse,
    DemoEnrollmentResponse,
)
from app.schemas.lesson import LessonProgressCreate, LessonProgressResponse
from app.services.assessment_service import (
    MINIMUM_SCORE,
    QUESTION_BANKS,
    QUESTION_VERSION,
    course_requires_assessment,
    grade_answers,
    public_questions,
)
from app.services.certificate_service import CertificateService, is_demo_certificate

router = APIRouter()

_DEMO_CLASS_LOCATION = "DEMO-EAD-ASSESSMENT"


async def _load_course(db: AsyncSession, course_id: UUID, tenant_id: UUID) -> Course:
    course = (
        await db.execute(
            select(Course).where(Course.id == course_id, Course.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course


async def _load_student(
    db: AsyncSession,
    tenant_id: UUID,
    current_user: dict,
) -> Student:
    if current_user.get("role") != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student access required",
        )
    try:
        user_id = UUID(current_user["user_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid student identity",
        ) from exc

    student = (
        await db.execute(
            select(Student).where(
                Student.user_id == user_id,
                Student.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found",
        )
    return student


async def _load_enrollment(
    db: AsyncSession,
    *,
    student_id: UUID,
    course_id: UUID,
    tenant_id: UUID,
) -> Enrollment:
    enrollment = (
        await db.execute(
            select(Enrollment)
            .join(Class, Enrollment.class_id == Class.id)
            .where(
                Enrollment.student_id == student_id,
                Enrollment.tenant_id == tenant_id,
                Class.course_id == course_id,
                Class.tenant_id == tenant_id,
                Enrollment.status.in_(
                    [EnrollmentStatus.CONFIRMADA, EnrollmentStatus.CONCLUIDA]
                ),
            )
            .order_by(
                (Enrollment.status == EnrollmentStatus.CONFIRMADA).desc(),
                Enrollment.enrollment_date.desc(),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active enrollment required for this course",
        )
    return enrollment


async def _student_course_context(
    db: AsyncSession,
    *,
    course_id: UUID,
    tenant_id: UUID,
    current_user: dict,
) -> tuple[Course, Student, Enrollment]:
    course = await _load_course(db, course_id, tenant_id)
    student = await _load_student(db, tenant_id, current_user)
    enrollment = await _load_enrollment(
        db,
        student_id=student.id,
        course_id=course_id,
        tenant_id=tenant_id,
    )
    return course, student, enrollment


async def _required_progress(
    db: AsyncSession,
    *,
    student_id: UUID,
    course_id: UUID,
    tenant_id: UUID,
) -> tuple[int, int]:
    required_total = (
        await db.scalar(
            select(func.count(Lesson.id)).where(
                Lesson.course_id == course_id,
                Lesson.tenant_id == tenant_id,
                Lesson.is_required.is_(True),
            )
        )
        or 0
    )
    completed_required = (
        await db.scalar(
            select(func.count(LessonProgress.id))
            .join(Lesson, LessonProgress.lesson_id == Lesson.id)
            .where(
                LessonProgress.student_id == student_id,
                LessonProgress.tenant_id == tenant_id,
                Lesson.course_id == course_id,
                Lesson.tenant_id == tenant_id,
                Lesson.is_required.is_(True),
                LessonProgress.completed.is_(True),
            )
        )
        or 0
    )
    return int(required_total), int(completed_required)


async def _load_attempt_for_student(
    db: AsyncSession,
    *,
    attempt_id: UUID,
    tenant_id: UUID,
    student_id: UUID,
) -> AssessmentAttempt:
    attempt = (
        await db.execute(
            select(AssessmentAttempt).where(
                AssessmentAttempt.id == attempt_id,
                AssessmentAttempt.tenant_id == tenant_id,
                AssessmentAttempt.student_id == student_id,
            )
        )
    ).scalar_one_or_none()
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment attempt not found",
        )
    return attempt


@router.get(
    "/courses/{course_id}/status",
    response_model=AssessmentStatusResponse,
)
async def assessment_status(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    course, student, enrollment = await _student_course_context(
        db,
        course_id=course_id,
        tenant_id=tenant_id,
        current_user=current_user,
    )

    if not course_requires_assessment(course.code):
        return AssessmentStatusResponse(required=False, lessons_complete=False)

    required_total, completed_required = await _required_progress(
        db,
        student_id=student.id,
        course_id=course.id,
        tenant_id=tenant_id,
    )
    lessons_complete = required_total > 0 and completed_required >= required_total

    attempts = list(
        (
            await db.execute(
                select(AssessmentAttempt)
                .where(
                    AssessmentAttempt.tenant_id == tenant_id,
                    AssessmentAttempt.enrollment_id == enrollment.id,
                    AssessmentAttempt.student_id == student.id,
                    AssessmentAttempt.course_id == course.id,
                )
                .order_by(AssessmentAttempt.attempt_number.desc())
            )
        ).scalars().all()
    )
    completed_attempts = [item for item in attempts if item.completed_at is not None]
    passed_attempts = [item for item in completed_attempts if item.passed]
    passed_attempt = passed_attempts[0] if passed_attempts else None
    best_score = max(
        (item.score for item in completed_attempts if item.score is not None),
        default=None,
    )

    evidence = (
        await db.execute(
            select(StudentSignatureEvidence).where(
                StudentSignatureEvidence.tenant_id == tenant_id,
                StudentSignatureEvidence.enrollment_id == enrollment.id,
                StudentSignatureEvidence.student_id == student.id,
            )
        )
    ).scalar_one_or_none()
    certificate = (
        await db.execute(
            select(Certificate).where(
                Certificate.tenant_id == tenant_id,
                Certificate.enrollment_id == enrollment.id,
                Certificate.status == "ACTIVE",
            )
        )
    ).scalar_one_or_none()

    passed = passed_attempt is not None
    return AssessmentStatusResponse(
        required=True,
        lessons_complete=lessons_complete,
        minimum_score=MINIMUM_SCORE,
        attempts=len(attempts),
        passed=passed,
        passed_attempt_id=passed_attempt.id if passed_attempt else None,
        best_score=best_score,
        confirmation_required=passed and evidence is None and certificate is None,
        completion_confirmed=evidence is not None,
        certificate_id=certificate.id if certificate else None,
        certificate_validation_code=certificate.validation_code if certificate else None,
    )


@router.post(
    "/courses/{course_id}/demo-enroll",
    response_model=DemoEnrollmentResponse,
)
async def demo_enroll(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a no-charge enrollment only in the explicitly enabled demo environment."""
    if not settings.DEMO_SEED_MODE or settings.ENVIRONMENT.lower() == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo enrollment is disabled in this environment",
        )

    tenant_id = get_current_tenant_id()
    course = await _load_course(db, course_id, tenant_id)
    if not course_requires_assessment(course.code):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo assessment journey is not configured for this course",
        )
    student = await _load_student(db, tenant_id, current_user)

    existing = (
        await db.execute(
            select(Enrollment)
            .join(Class, Enrollment.class_id == Class.id)
            .where(
                Enrollment.student_id == student.id,
                Enrollment.tenant_id == tenant_id,
                Class.course_id == course.id,
                Class.tenant_id == tenant_id,
                Enrollment.status.in_(
                    [EnrollmentStatus.CONFIRMADA, EnrollmentStatus.CONCLUIDA]
                ),
            )
            .order_by(Enrollment.enrollment_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing:
        return DemoEnrollmentResponse(
            enrollment_id=existing.id,
            course_id=course.id,
            status=existing.status.value,
            created=False,
        )

    admin = (
        await db.execute(
            select(User)
            .where(
                User.tenant_id == tenant_id,
                User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]),
                User.is_active.is_(True),
            )
            .order_by(User.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Demo enrollment requires an active tenant administrator",
        )

    demo_class = (
        await db.execute(
            select(Class).where(
                Class.tenant_id == tenant_id,
                Class.course_id == course.id,
                Class.location == _DEMO_CLASS_LOCATION,
            )
        )
    ).scalar_one_or_none()
    if not demo_class:
        now = utc_now()
        demo_class = Class(
            tenant_id=tenant_id,
            course_id=course.id,
            responsible_admin_id=admin.id,
            start_date=now.date(),
            end_date=(now + timedelta(days=90)).date(),
            max_students=1000,
            location=_DEMO_CLASS_LOCATION,
            status=ClassStatus.ABERTA,
            description="Turma técnica de homologação — sem cobrança.",
        )
        db.add(demo_class)
        await db.flush()

    enrollment = Enrollment(
        tenant_id=tenant_id,
        student_id=student.id,
        class_id=demo_class.id,
        status=EnrollmentStatus.CONFIRMADA,
        price=0.0,
    )
    db.add(enrollment)
    await db.commit()
    await db.refresh(enrollment)
    return DemoEnrollmentResponse(
        enrollment_id=enrollment.id,
        course_id=course.id,
        status=enrollment.status.value,
        created=True,
    )


@router.post(
    "/lessons/{lesson_id}/progress",
    response_model=LessonProgressResponse,
)
async def assessment_lesson_progress(
    lesson_id: UUID,
    progress_data: LessonProgressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Persist progress without auto-issuing a certificate at 100% lessons."""
    tenant_id = get_current_tenant_id()
    lesson = (
        await db.execute(
            select(Lesson).where(
                Lesson.id == lesson_id,
                Lesson.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    course = await _load_course(db, lesson.course_id, tenant_id)
    if not course_requires_assessment(course.code):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment progress route is not configured for this course",
        )
    student = await _load_student(db, tenant_id, current_user)
    await _load_enrollment(
        db,
        student_id=student.id,
        course_id=course.id,
        tenant_id=tenant_id,
    )

    if progress_data.watched_seconds < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="watched_seconds must be non-negative",
        )
    if (
        lesson.duration_seconds is not None
        and progress_data.watched_seconds > lesson.duration_seconds
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="watched_seconds cannot exceed lesson duration",
        )

    progress = (
        await db.execute(
            select(LessonProgress).where(
                LessonProgress.student_id == student.id,
                LessonProgress.lesson_id == lesson.id,
                LessonProgress.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not progress:
        progress = LessonProgress(
            tenant_id=tenant_id,
            student_id=student.id,
            lesson_id=lesson.id,
            watched_seconds=progress_data.watched_seconds,
            completed=False,
        )
        db.add(progress)
    else:
        progress.watched_seconds = max(
            progress.watched_seconds,
            progress_data.watched_seconds,
        )

    should_complete = progress_data.completed
    if (
        not should_complete
        and lesson.content_type == LessonContentType.UPLOAD
        and lesson.duration_seconds
    ):
        should_complete = progress.watched_seconds >= int(lesson.duration_seconds * 0.9)
    if should_complete and not progress.completed:
        progress.completed = True
        progress.completed_at = utc_now()

    await db.commit()
    await db.refresh(progress)
    return progress


@router.post(
    "/courses/{course_id}/start",
    response_model=AssessmentStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_assessment(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    course, student, enrollment = await _student_course_context(
        db,
        course_id=course_id,
        tenant_id=tenant_id,
        current_user=current_user,
    )
    if not course_requires_assessment(course.code):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment is not configured for this course",
        )

    required_total, completed_required = await _required_progress(
        db,
        student_id=student.id,
        course_id=course.id,
        tenant_id=tenant_id,
    )
    if required_total == 0 or completed_required < required_total:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete all required lessons before starting the assessment",
        )

    passed = (
        await db.execute(
            select(AssessmentAttempt)
            .where(
                AssessmentAttempt.tenant_id == tenant_id,
                AssessmentAttempt.enrollment_id == enrollment.id,
                AssessmentAttempt.passed.is_(True),
                AssessmentAttempt.completed_at.is_not(None),
            )
            .order_by(AssessmentAttempt.attempt_number.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if passed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assessment already passed; confirm course completion",
        )

    unfinished = (
        await db.execute(
            select(AssessmentAttempt)
            .where(
                AssessmentAttempt.tenant_id == tenant_id,
                AssessmentAttempt.enrollment_id == enrollment.id,
                AssessmentAttempt.student_id == student.id,
                AssessmentAttempt.course_id == course.id,
                AssessmentAttempt.completed_at.is_(None),
            )
            .order_by(AssessmentAttempt.attempt_number.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if unfinished:
        return AssessmentStartResponse(
            attempt_id=unfinished.id,
            course_id=course.id,
            attempt_number=unfinished.attempt_number,
            minimum_score=unfinished.minimum_score,
            question_version=unfinished.question_version,
            questions=public_questions(course.code),
            started_at=unfinished.started_at,
        )

    last_number = (
        await db.scalar(
            select(func.coalesce(func.max(AssessmentAttempt.attempt_number), 0)).where(
                AssessmentAttempt.tenant_id == tenant_id,
                AssessmentAttempt.enrollment_id == enrollment.id,
            )
        )
        or 0
    )
    questions = public_questions(course.code)
    attempt = AssessmentAttempt(
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
        student_id=student.id,
        course_id=course.id,
        attempt_number=int(last_number) + 1,
        question_version=QUESTION_VERSION,
        total_questions=len(questions),
        minimum_score=MINIMUM_SCORE,
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return AssessmentStartResponse(
        attempt_id=attempt.id,
        course_id=course.id,
        attempt_number=attempt.attempt_number,
        minimum_score=attempt.minimum_score,
        question_version=attempt.question_version,
        questions=questions,
        started_at=attempt.started_at,
    )


@router.post(
    "/attempts/{attempt_id}/submit",
    response_model=AssessmentResultResponse,
)
async def submit_assessment(
    attempt_id: UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    student = await _load_student(db, tenant_id, current_user)
    attempt = await _load_attempt_for_student(
        db,
        attempt_id=attempt_id,
        tenant_id=tenant_id,
        student_id=student.id,
    )
    if attempt.completed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assessment attempt was already submitted",
        )

    course = await _load_course(db, attempt.course_id, tenant_id)
    bank = QUESTION_BANKS.get(course.code)
    if not bank:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment is not configured for this course",
        )

    answers = payload.get("answers") if isinstance(payload, dict) else None
    if not isinstance(answers, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="answers must be an object",
        )
    expected_ids = {item["id"] for item in bank}
    if set(answers) != expected_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Answer every assessment question exactly once",
        )
    for item in bank:
        value = answers.get(item["id"])
        if not isinstance(value, int) or value < 0 or value >= len(item["options"]):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid option for question {item['id']}",
            )

    correct, total, score_value, passed = grade_answers(course.code, answers)
    attempt.answers = answers
    attempt.correct_answers = correct
    attempt.total_questions = total
    attempt.score = score_value
    attempt.passed = passed
    attempt.completed_at = utc_now()
    await db.commit()
    await db.refresh(attempt)
    return AssessmentResultResponse(
        attempt_id=attempt.id,
        score=attempt.score,
        minimum_score=attempt.minimum_score,
        correct_answers=attempt.correct_answers,
        total_questions=attempt.total_questions,
        passed=attempt.passed,
        status="PASSED" if attempt.passed else "FAILED",
        completed_at=attempt.completed_at,
    )


@router.post(
    "/attempts/{attempt_id}/confirm",
    response_model=CompletionConfirmationResponse,
)
async def confirm_completion(
    attempt_id: UUID,
    payload: CompletionConfirmationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if not payload.declaration_accepted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Completion declaration must be accepted",
        )

    tenant_id = get_current_tenant_id()
    student = await _load_student(db, tenant_id, current_user)
    attempt = await _load_attempt_for_student(
        db,
        attempt_id=attempt_id,
        tenant_id=tenant_id,
        student_id=student.id,
    )
    if attempt.completed_at is None or not attempt.passed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A passing assessment attempt is required",
        )

    course = await _load_course(db, attempt.course_id, tenant_id)
    enrollment = await _load_enrollment(
        db,
        student_id=student.id,
        course_id=course.id,
        tenant_id=tenant_id,
    )
    if enrollment.id != attempt.enrollment_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assessment attempt does not match the active enrollment",
        )

    required_total, completed_required = await _required_progress(
        db,
        student_id=student.id,
        course_id=course.id,
        tenant_id=tenant_id,
    )
    if required_total == 0 or completed_required < required_total:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Required lessons are no longer complete",
        )

    user = (
        await db.execute(
            select(User).where(
                User.id == UUID(current_user["user_id"]),
                User.tenant_id == tenant_id,
                User.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if (
        not user
        or not user.password_hash
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password confirmation",
        )

    evidence = (
        await db.execute(
            select(StudentSignatureEvidence).where(
                StudentSignatureEvidence.tenant_id == tenant_id,
                StudentSignatureEvidence.enrollment_id == enrollment.id,
            )
        )
    ).scalar_one_or_none()
    if not evidence:
        evidence = StudentSignatureEvidence(
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            student_id=student.id,
            course_id=course.id,
            assessment_attempt_id=attempt.id,
            declaration_version="nr1-demo-v1",
            auth_method="PASSWORD_REAUTH",
        )
        db.add(evidence)

    enrollment.status = EnrollmentStatus.CONCLUIDA

    certificate = (
        await db.execute(
            select(Certificate).where(
                Certificate.tenant_id == tenant_id,
                Certificate.enrollment_id == enrollment.id,
                Certificate.status == "ACTIVE",
            )
        )
    ).scalar_one_or_none()
    if not certificate:
        certificate = await CertificateService.issue_certificate(
            db,
            tenant_id=tenant_id,
            enrollment=enrollment,
            student=student,
            course_id=course.id,
            course_validity_days=course.certificate_validity_days,
            actor_id=user.id,
            reason="student assessment completion confirmation",
            demo=True,
        )

    await db.commit()
    await db.refresh(certificate)
    return CompletionConfirmationResponse(
        confirmed=True,
        certificate_id=certificate.id,
        certificate_number=certificate.certificate_number,
        validation_code=certificate.validation_code,
        is_demo=is_demo_certificate(certificate),
    )
