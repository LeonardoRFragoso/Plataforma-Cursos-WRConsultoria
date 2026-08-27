"""Course content plus NR-01 learning-assessment journey endpoints."""
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    get_current_admin,
    get_current_tenant_id,
    get_current_user,
    verify_password,
)
from app.core.utils import utc_now
from app.models.assessment import AssessmentAttempt, StudentSignatureEvidence
from app.models.certificate import Certificate
from app.models.class_model import Class, ClassStatus
from app.models.course import Course
from app.models.course_content_profile import CourseContentProfile
from app.models.enrollment import Enrollment, EnrollmentSource, EnrollmentStatus
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
from app.schemas.course_content_profile import (
    CourseContentProfileCreate,
    CourseContentProfileResponse,
    CourseContentProfileUpdate,
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


@router.get("/courses/{course_id}/content-profile", response_model=CourseContentProfileResponse)
async def get_content_profile(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = get_current_tenant_id()
    result = await db.execute(
        select(CourseContentProfile).where(
            CourseContentProfile.course_id == course_id,
            CourseContentProfile.tenant_id == tenant_id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content profile not found")
    return profile


@router.post(
    "/courses/{course_id}/content-profile",
    response_model=CourseContentProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_content_profile(
    course_id: UUID,
    profile_data: CourseContentProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    course = (
        await db.execute(select(Course).where(Course.id == course_id, Course.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    existing = (
        await db.execute(
            select(CourseContentProfile).where(
                CourseContentProfile.course_id == course_id,
                CourseContentProfile.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Content profile already exists for this course")
    data = profile_data.model_dump(exclude={"course_id"})
    profile = CourseContentProfile(tenant_id=tenant_id, course_id=course_id, **data)
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.put("/courses/{course_id}/content-profile", response_model=CourseContentProfileResponse)
async def update_content_profile(
    course_id: UUID,
    profile_data: CourseContentProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    result = await db.execute(
        select(CourseContentProfile).where(
            CourseContentProfile.course_id == course_id,
            CourseContentProfile.tenant_id == tenant_id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content profile not found")
    for key, value in profile_data.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    await db.commit()
    await db.refresh(profile)
    return profile


async def _student(db: AsyncSession, tenant_id: UUID, current_user: dict) -> Student:
    if current_user.get("role") != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student access required")
    student = (
        await db.execute(
            select(Student).where(
                Student.tenant_id == tenant_id,
                Student.user_id == UUID(current_user["user_id"]),
            )
        )
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")
    return student


async def _course(db: AsyncSession, tenant_id: UUID, course_id: UUID) -> Course:
    course = (
        await db.execute(
            select(Course).where(Course.id == course_id, Course.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course


async def _enrollment(
    db: AsyncSession, tenant_id: UUID, student_id: UUID, course_id: UUID
) -> Enrollment:
    enrollment = (
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
            .order_by(Enrollment.enrollment_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if not enrollment:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Enrollment required")
    return enrollment


async def _lessons_complete(
    db: AsyncSession, tenant_id: UUID, student_id: UUID, course_id: UUID
) -> bool:
    required = await db.scalar(
        select(func.count(Lesson.id)).where(
            Lesson.tenant_id == tenant_id,
            Lesson.course_id == course_id,
            Lesson.is_required.is_(True),
        )
    ) or 0
    completed = await db.scalar(
        select(func.count(LessonProgress.id))
        .join(Lesson, LessonProgress.lesson_id == Lesson.id)
        .where(
            LessonProgress.tenant_id == tenant_id,
            LessonProgress.student_id == student_id,
            Lesson.course_id == course_id,
            Lesson.is_required.is_(True),
            LessonProgress.completed.is_(True),
        )
    ) or 0
    return required > 0 and completed >= required


@router.post(
    "/assessments/courses/{course_id}/demo-enroll",
    response_model=DemoEnrollmentResponse,
)
async def demo_enroll_student(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Activate a no-payment enrollment only in the staging/demo environment."""
    if not settings.DEMO_SEED_MODE or settings.ENVIRONMENT.lower() == "production":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demo enrollment unavailable")
    tenant_id = get_current_tenant_id()
    student = await _student(db, tenant_id, current_user)
    course = await _course(db, tenant_id, course_id)
    if not course_requires_assessment(course.code):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Course is not enabled for the NR demo journey")

    existing = (
        await db.execute(
            select(Enrollment)
            .join(Class, Enrollment.class_id == Class.id)
            .where(
                Enrollment.tenant_id == tenant_id,
                Enrollment.student_id == student.id,
                Class.tenant_id == tenant_id,
                Class.course_id == course_id,
            )
            .order_by(Enrollment.enrollment_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing:
        if existing.status == EnrollmentStatus.PENDENTE:
            existing.status = EnrollmentStatus.CONFIRMADA
            await db.commit()
        return DemoEnrollmentResponse(
            enrollment_id=existing.id,
            course_id=course_id,
            status=existing.status.value,
            created=False,
        )

    demo_class = (
        await db.execute(
            select(Class).where(
                Class.tenant_id == tenant_id,
                Class.course_id == course_id,
                Class.location == "DEMO-EAD-NR1",
                Class.status.in_([ClassStatus.ABERTA, ClassStatus.EM_ANDAMENTO]),
            ).limit(1)
        )
    ).scalar_one_or_none()
    if not demo_class:
        admin = (
            await db.execute(
                select(User).where(
                    User.tenant_id == tenant_id,
                    User.role == UserRole.ADMIN,
                    User.is_active.is_(True),
                ).limit(1)
            )
        ).scalar_one_or_none()
        if not admin:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Demo admin not configured")
        today = utc_now().date()
        demo_class = Class(
            tenant_id=tenant_id,
            course_id=course_id,
            responsible_admin_id=admin.id,
            start_date=today,
            end_date=today + timedelta(days=90),
            max_students=999,
            location="DEMO-EAD-NR1",
            status=ClassStatus.EM_ANDAMENTO,
            description="Turma técnica de homologação do fluxo EAD NR-01.",
        )
        db.add(demo_class)
        await db.flush()

    enrollment = Enrollment(
        tenant_id=tenant_id,
        student_id=student.id,
        class_id=demo_class.id,
        status=EnrollmentStatus.CONFIRMADA,
        source=EnrollmentSource.INDIVIDUAL,
        price=0.0,
    )
    db.add(enrollment)
    await db.commit()
    await db.refresh(enrollment)
    return DemoEnrollmentResponse(
        enrollment_id=enrollment.id,
        course_id=course_id,
        status=enrollment.status.value,
        created=True,
    )


@router.post(
    "/assessments/lessons/{lesson_id}/progress",
    response_model=LessonProgressResponse,
)
async def save_regulatory_lesson_progress(
    lesson_id: UUID,
    progress_data: LessonProgressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Assessment-aware progress: records completion without issuing a premature certificate."""
    tenant_id = get_current_tenant_id()
    student = await _student(db, tenant_id, current_user)
    lesson = (
        await db.execute(
            select(Lesson).where(Lesson.id == lesson_id, Lesson.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    await _enrollment(db, tenant_id, student.id, lesson.course_id)
    if progress_data.watched_seconds < 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="watched_seconds must be non-negative")
    if lesson.duration_seconds is not None and progress_data.watched_seconds > lesson.duration_seconds:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="watched_seconds cannot exceed lesson duration")

    progress = (
        await db.execute(
            select(LessonProgress).where(
                LessonProgress.tenant_id == tenant_id,
                LessonProgress.student_id == student.id,
                LessonProgress.lesson_id == lesson_id,
            )
        )
    ).scalar_one_or_none()
    if not progress:
        progress = LessonProgress(
            tenant_id=tenant_id,
            student_id=student.id,
            lesson_id=lesson_id,
            watched_seconds=progress_data.watched_seconds,
            completed=False,
        )
        db.add(progress)
    else:
        progress.watched_seconds = max(progress.watched_seconds, progress_data.watched_seconds)

    should_complete = bool(progress_data.completed)
    if lesson.content_type == LessonContentType.UPLOAD and lesson.duration_seconds:
        should_complete = should_complete or progress.watched_seconds >= int(lesson.duration_seconds * 0.9)
    if should_complete and not progress.completed:
        progress.completed = True
        progress.completed_at = utc_now()

    await db.commit()
    await db.refresh(progress)
    return progress


@router.get(
    "/assessments/courses/{course_id}/status",
    response_model=AssessmentStatusResponse,
)
async def assessment_status(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    student = await _student(db, tenant_id, current_user)
    course = await _course(db, tenant_id, course_id)
    enrollment = await _enrollment(db, tenant_id, student.id, course_id)
    lessons_complete = await _lessons_complete(db, tenant_id, student.id, course_id)
    required = course_requires_assessment(course.code)

    attempts = list((await db.execute(
        select(AssessmentAttempt).where(
            AssessmentAttempt.tenant_id == tenant_id,
            AssessmentAttempt.enrollment_id == enrollment.id,
        ).order_by(AssessmentAttempt.attempt_number.desc())
    )).scalars().all())
    passed_attempts = [attempt for attempt in attempts if attempt.passed and attempt.completed_at]
    best_score = max((attempt.score or 0 for attempt in attempts if attempt.completed_at), default=None)
    evidence = (
        await db.execute(
            select(StudentSignatureEvidence).where(
                StudentSignatureEvidence.tenant_id == tenant_id,
                StudentSignatureEvidence.enrollment_id == enrollment.id,
            )
        )
    ).scalar_one_or_none()
    certificate = (
        await db.execute(
            select(Certificate).where(
                Certificate.tenant_id == tenant_id,
                Certificate.enrollment_id == enrollment.id,
                Certificate.status == "ACTIVE",
            ).order_by(Certificate.issued_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    passed = bool(passed_attempts)
    return AssessmentStatusResponse(
        required=required,
        lessons_complete=lessons_complete,
        minimum_score=MINIMUM_SCORE,
        attempts=len([a for a in attempts if a.completed_at]),
        passed=passed,
        best_score=best_score,
        confirmation_required=required and lessons_complete and passed and evidence is None,
        completion_confirmed=evidence is not None,
        certificate_id=certificate.id if certificate else None,
        certificate_validation_code=certificate.validation_code if certificate else None,
    )


@router.post(
    "/assessments/courses/{course_id}/start",
    response_model=AssessmentStartResponse,
)
async def start_assessment(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    student = await _student(db, tenant_id, current_user)
    course = await _course(db, tenant_id, course_id)
    enrollment = await _enrollment(db, tenant_id, student.id, course_id)
    if not course_requires_assessment(course.code):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not configured")
    if not await _lessons_complete(db, tenant_id, student.id, course_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Complete all required lessons before the final assessment")

    open_attempt = (
        await db.execute(
            select(AssessmentAttempt).where(
                AssessmentAttempt.tenant_id == tenant_id,
                AssessmentAttempt.enrollment_id == enrollment.id,
                AssessmentAttempt.completed_at.is_(None),
            ).order_by(AssessmentAttempt.attempt_number.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if open_attempt:
        attempt = open_attempt
    else:
        current_max = await db.scalar(
            select(func.coalesce(func.max(AssessmentAttempt.attempt_number), 0)).where(
                AssessmentAttempt.tenant_id == tenant_id,
                AssessmentAttempt.enrollment_id == enrollment.id,
            )
        ) or 0
        attempt = AssessmentAttempt(
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            student_id=student.id,
            course_id=course_id,
            attempt_number=int(current_max) + 1,
            question_version=QUESTION_VERSION,
            total_questions=len(QUESTION_BANKS[course.code]),
            minimum_score=MINIMUM_SCORE,
            started_at=utc_now(),
        )
        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)

    return AssessmentStartResponse(
        attempt_id=attempt.id,
        course_id=course_id,
        attempt_number=attempt.attempt_number,
        minimum_score=MINIMUM_SCORE,
        question_version=QUESTION_VERSION,
        questions=public_questions(course.code),
        started_at=attempt.started_at,
    )


@router.post(
    "/assessments/attempts/{attempt_id}/submit",
    response_model=AssessmentResultResponse,
)
async def submit_assessment(
    attempt_id: UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    student = await _student(db, tenant_id, current_user)
    attempt = (
        await db.execute(
            select(AssessmentAttempt).where(
                AssessmentAttempt.id == attempt_id,
                AssessmentAttempt.tenant_id == tenant_id,
                AssessmentAttempt.student_id == student.id,
            )
        )
    ).scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment attempt not found")
    if attempt.completed_at:
        return AssessmentResultResponse(
            attempt_id=attempt.id,
            score=attempt.score or 0,
            minimum_score=attempt.minimum_score,
            correct_answers=attempt.correct_answers or 0,
            total_questions=attempt.total_questions,
            passed=attempt.passed,
            status="SATISFATORIO" if attempt.passed else "INSATISFATORIO",
            completed_at=attempt.completed_at,
        )
    answers = payload.get("answers") if isinstance(payload, dict) else None
    if not isinstance(answers, dict):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="answers is required")
    course = await _course(db, tenant_id, attempt.course_id)
    bank = QUESTION_BANKS.get(course.code, [])
    expected_ids = {item["id"] for item in bank}
    if set(answers.keys()) != expected_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Answer every question before submitting")
    for item in bank:
        answer = answers.get(item["id"])
        if not isinstance(answer, int) or answer < 0 or answer >= len(item["options"]):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid answer for {item['id']}")

    correct, total, score_value, passed = grade_answers(course.code, answers)
    attempt.answers = answers
    attempt.correct_answers = correct
    attempt.total_questions = total
    attempt.score = score_value
    attempt.passed = passed
    attempt.completed_at = utc_now()
    await db.commit()
    return AssessmentResultResponse(
        attempt_id=attempt.id,
        score=score_value,
        minimum_score=attempt.minimum_score,
        correct_answers=correct,
        total_questions=total,
        passed=passed,
        status="SATISFATORIO" if passed else "INSATISFATORIO",
        completed_at=attempt.completed_at,
    )


@router.post(
    "/assessments/attempts/{attempt_id}/confirm",
    response_model=CompletionConfirmationResponse,
)
async def confirm_completion_and_issue_certificate(
    attempt_id: UUID,
    payload: CompletionConfirmationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if not payload.declaration_accepted:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="You must accept the completion declaration")
    tenant_id = get_current_tenant_id()
    student = await _student(db, tenant_id, current_user)
    attempt = (
        await db.execute(
            select(AssessmentAttempt).where(
                AssessmentAttempt.id == attempt_id,
                AssessmentAttempt.tenant_id == tenant_id,
                AssessmentAttempt.student_id == student.id,
            )
        )
    ).scalar_one_or_none()
    if not attempt or not attempt.completed_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Completed assessment not found")
    if not attempt.passed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A satisfactory final assessment is required")
    enrollment = await _enrollment(db, tenant_id, student.id, attempt.course_id)
    if attempt.enrollment_id != enrollment.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Assessment does not belong to this enrollment")
    user = (
        await db.execute(
            select(User).where(User.id == UUID(current_user["user_id"]), User.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Password confirmation failed")

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
            course_id=attempt.course_id,
            assessment_attempt_id=attempt.id,
            declaration_version="nr1-demo-v1",
            auth_method="PASSWORD_REAUTH",
            accepted_at=utc_now(),
        )
        db.add(evidence)

    enrollment.status = EnrollmentStatus.CONCLUIDA
    certificate = (
        await db.execute(
            select(Certificate).where(
                Certificate.tenant_id == tenant_id,
                Certificate.enrollment_id == enrollment.id,
                Certificate.status == "ACTIVE",
            ).order_by(Certificate.issued_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if not certificate:
        course = await _course(db, tenant_id, attempt.course_id)
        demo = bool(settings.DEMO_SEED_MODE or settings.ENVIRONMENT.lower() != "production")
        certificate = await CertificateService.issue_certificate(
            db,
            tenant_id=tenant_id,
            enrollment=enrollment,
            student=student,
            course_id=course.id,
            course_validity_days=course.certificate_validity_days,
            actor_id=UUID(current_user["user_id"]),
            demo=demo,
            reason=f"final_assessment={attempt.score};declaration=nr1-demo-v1",
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
