from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.lessons import _maybe_create_certificate
from app.core.database import get_db
from app.core.proxy import get_client_ip
from app.core.security import get_current_tenant_id, get_current_user
from app.core.storage import generate_watch_url
from app.core.utils import utc_now
from app.models.class_model import Class
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.lesson import Lesson, LessonContentType, LessonProgress
from app.models.student import Student
from app.schemas.lesson import LessonProgressCreate, LessonProgressResponse
from app.services.assessment_service import course_requires_assessment
from app.services.compliance_service import ComplianceService
from app.services.learning_service import completion_allowed, require_previous_lesson_completed

router = APIRouter()


async def _student(db: AsyncSession, tenant_id: UUID, current_user: dict) -> Student:
    if current_user.get("role") != "student":
        raise HTTPException(status_code=403, detail="Student access required")
    student = (
        await db.execute(
            select(Student).where(
                Student.tenant_id == tenant_id,
                Student.user_id == UUID(current_user["user_id"]),
            )
        )
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    return student


async def _active_enrollment(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    student_id: UUID,
    course_id: UUID,
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
        raise HTTPException(status_code=403, detail="Active enrollment required for this course")
    return enrollment


async def _context(
    db: AsyncSession,
    *,
    lesson_id: UUID,
    tenant_id: UUID,
    current_user: dict,
) -> tuple[Lesson, Student | None, Enrollment | None, Course]:
    lesson = (
        await db.execute(
            select(Lesson).where(Lesson.id == lesson_id, Lesson.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    course = (
        await db.execute(
            select(Course).where(Course.id == lesson.course_id, Course.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if current_user.get("role") in ("admin", "super_admin"):
        return lesson, None, None, course

    student = await _student(db, tenant_id, current_user)
    enrollment = await _active_enrollment(
        db,
        tenant_id=tenant_id,
        student_id=student.id,
        course_id=course.id,
    )
    await require_previous_lesson_completed(
        db,
        tenant_id=tenant_id,
        student_id=student.id,
        lesson=lesson,
    )
    return lesson, student, enrollment, course


def _audit_request(request: Request) -> tuple[str | None, str | None, str | None]:
    session_id = request.headers.get("X-Training-Session")
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    return session_id, ip_address, user_agent


@router.get("/lessons/{lesson_id}/watch-url")
async def guarded_watch_url(
    lesson_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    lesson, student, enrollment, course = await _context(
        db,
        lesson_id=lesson_id,
        tenant_id=tenant_id,
        current_user=current_user,
    )

    if lesson.content_type in (LessonContentType.YOUTUBE, LessonContentType.VIMEO):
        watch_url = lesson.video_url
    elif lesson.storage_key:
        watch_url = await generate_watch_url(storage_key=lesson.storage_key)
    else:
        raise HTTPException(status_code=404, detail="Video not uploaded yet")

    if student and enrollment:
        session_id, ip_address, user_agent = _audit_request(request)
        await ComplianceService.log_event(
            db,
            tenant_id=tenant_id,
            student_id=student.id,
            enrollment_id=enrollment.id,
            course_id=course.id,
            lesson_id=lesson.id,
            event_type="LESSON_OPENED",
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await db.commit()
    return {"watch_url": watch_url}


async def _persist_guarded_progress(
    *,
    lesson_id: UUID,
    progress_data: LessonProgressCreate,
    request: Request,
    db: AsyncSession,
    current_user: dict,
) -> LessonProgress:
    tenant_id = get_current_tenant_id()
    lesson, student, enrollment, course = await _context(
        db,
        lesson_id=lesson_id,
        tenant_id=tenant_id,
        current_user=current_user,
    )
    if student is None or enrollment is None:
        raise HTTPException(status_code=403, detail="Student progress requires a student account")

    if progress_data.watched_seconds < 0:
        raise HTTPException(status_code=422, detail="watched_seconds must be non-negative")
    if lesson.duration_seconds is not None and progress_data.watched_seconds > lesson.duration_seconds:
        raise HTTPException(status_code=422, detail="watched_seconds cannot exceed lesson duration")

    progress = (
        await db.execute(
            select(LessonProgress).where(
                LessonProgress.tenant_id == tenant_id,
                LessonProgress.student_id == student.id,
                LessonProgress.lesson_id == lesson.id,
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
        progress.watched_seconds = max(progress.watched_seconds, progress_data.watched_seconds)

    if progress_data.completed and not completion_allowed(
        lesson=lesson,
        requested_completed=True,
        watched_seconds=progress.watched_seconds,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O vídeo precisa chegar ao final antes de esta aula ser concluída",
        )

    became_completed = False
    if completion_allowed(
        lesson=lesson,
        requested_completed=progress_data.completed,
        watched_seconds=progress.watched_seconds,
    ) and not progress.completed:
        progress.completed = True
        progress.completed_at = utc_now()
        became_completed = True

    session_id, ip_address, user_agent = _audit_request(request)
    await ComplianceService.log_event(
        db,
        tenant_id=tenant_id,
        student_id=student.id,
        enrollment_id=enrollment.id,
        course_id=course.id,
        lesson_id=lesson.id,
        event_type="LESSON_COMPLETED" if became_completed else "PROGRESS_SAVED",
        session_id=session_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"watched_seconds": progress.watched_seconds},
    )

    await db.flush()
    # Assessment-managed courses must never receive a legacy certificate by
    # merely completing the lessons. Their certificate path is assessment ->
    # identity confirmation -> compliance eligibility.
    if progress.completed and not course_requires_assessment(course.code):
        await _maybe_create_certificate(db, student.id, course.id, tenant_id)

    await db.commit()
    await db.refresh(progress)
    return progress


@router.post("/lessons/{lesson_id}/progress", response_model=LessonProgressResponse)
async def guarded_lesson_progress(
    lesson_id: UUID,
    progress_data: LessonProgressCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return await _persist_guarded_progress(
        lesson_id=lesson_id,
        progress_data=progress_data,
        request=request,
        db=db,
        current_user=current_user,
    )


@router.post("/assessments/lessons/{lesson_id}/progress", response_model=LessonProgressResponse)
async def guarded_assessment_progress(
    lesson_id: UUID,
    progress_data: LessonProgressCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return await _persist_guarded_progress(
        lesson_id=lesson_id,
        progress_data=progress_data,
        request=request,
        db=db,
        current_user=current_user,
    )
