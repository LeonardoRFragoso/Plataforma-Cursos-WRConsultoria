"""Compatibility guards for legacy routes that predate regulatory completion.

These routes intentionally use the same public paths and are registered before
legacy routers. Non-regulatory requests delegate to the original handlers.
Regulatory requests are handled here so old clients cannot bypass the central
state machine while the legacy endpoints remain available to existing courses.
They are hidden from OpenAPI to avoid duplicate documentation entries.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes import certificates as legacy_certificates
from app.api.routes import lessons as legacy_lessons
from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id, get_current_user
from app.core.utils import utc_now
from app.models.class_model import Class
from app.models.compliance import CourseComplianceProfile
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.lesson import Lesson, LessonContentType, LessonProgress
from app.models.student import Student
from app.models.training_evidence import RegulatoryCompletionState, TrainingEventType
from app.schemas.certificate import CertificateCreate
from app.schemas.lesson import CourseProgressDetailResponse, LessonProgressCreate, LessonProgressResponse
from app.services.training_evidence_service import (
    evaluate_regulatory_state,
    find_active_enrollment,
    record_training_event,
)

router = APIRouter(include_in_schema=False)


async def _profile_for_course(db: AsyncSession, tenant_id: UUID, course_id: UUID):
    return (
        await db.execute(
            select(CourseComplianceProfile).where(
                CourseComplianceProfile.tenant_id == tenant_id,
                CourseComplianceProfile.course_id == course_id,
            )
        )
    ).scalar_one_or_none()


async def _student_for_user(db: AsyncSession, tenant_id: UUID, current_user: dict):
    if current_user.get("role") != "student":
        return None
    return (
        await db.execute(
            select(Student).where(
                Student.tenant_id == tenant_id,
                Student.user_id == UUID(current_user["user_id"]),
            )
        )
    ).scalar_one_or_none()


@router.post("/lessons/{lesson_id}/progress", response_model=LessonProgressResponse)
async def guarded_lesson_progress(
    lesson_id: UUID,
    progress_data: LessonProgressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    lesson = (
        await db.execute(
            select(Lesson).where(Lesson.id == lesson_id, Lesson.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    profile = await _profile_for_course(db, tenant_id, lesson.course_id)
    if profile is None:
        return await legacy_lessons.update_lesson_progress(
            lesson_id=lesson_id,
            progress_data=progress_data,
            db=db,
            current_user=current_user,
        )

    student = await _student_for_user(db, tenant_id, current_user)
    if not student:
        raise HTTPException(status_code=403, detail="Student access required")
    enrollment = await find_active_enrollment(
        db,
        tenant_id=tenant_id,
        student_id=student.id,
        course_id=lesson.course_id,
    )
    if not enrollment:
        # Free previews remain a legacy/non-evidence interaction because there
        # is no enrollment to which regulatory evidence can be attached.
        if lesson.is_free_preview:
            return await legacy_lessons.update_lesson_progress(
                lesson_id=lesson_id,
                progress_data=progress_data,
                db=db,
                current_user=current_user,
            )
        raise HTTPException(status_code=403, detail="Active enrollment required")

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
    old_watched = progress.watched_seconds if progress else 0
    was_completed = bool(progress and progress.completed)
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

    should_complete = progress_data.completed
    if not should_complete and lesson.content_type == LessonContentType.UPLOAD and lesson.duration_seconds:
        should_complete = progress.watched_seconds >= int(lesson.duration_seconds * 0.9)
    if should_complete and not progress.completed:
        progress.completed = True
        progress.completed_at = utc_now()
    await db.flush()

    if progress.watched_seconds > old_watched:
        await record_training_event(
            db,
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            student_id=student.id,
            course_id=lesson.course_id,
            lesson_id=lesson.id,
            actor_user_id=student.user_id,
            event_type=TrainingEventType.PROGRESS_UPDATED,
            details={"watched_seconds": progress.watched_seconds},
        )
    if progress.completed and not was_completed:
        await record_training_event(
            db,
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            student_id=student.id,
            course_id=lesson.course_id,
            lesson_id=lesson.id,
            actor_user_id=student.user_id,
            event_type=TrainingEventType.LESSON_COMPLETED,
        )
    await evaluate_regulatory_state(
        db,
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
    )
    await db.commit()
    await db.refresh(progress)
    return progress


@router.get("/lessons/{lesson_id}/watch-url")
async def guarded_watch_url(
    lesson_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await legacy_lessons.get_lesson_watch_url(
        lesson_id=lesson_id,
        db=db,
        current_user=current_user,
    )
    tenant_id = get_current_tenant_id()
    lesson = (
        await db.execute(
            select(Lesson).where(Lesson.id == lesson_id, Lesson.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not lesson:
        return result
    profile = await _profile_for_course(db, tenant_id, lesson.course_id)
    student = await _student_for_user(db, tenant_id, current_user)
    if profile and student:
        enrollment = await find_active_enrollment(
            db,
            tenant_id=tenant_id,
            student_id=student.id,
            course_id=lesson.course_id,
        )
        if enrollment:
            await record_training_event(
                db,
                tenant_id=tenant_id,
                enrollment_id=enrollment.id,
                student_id=student.id,
                course_id=lesson.course_id,
                lesson_id=lesson.id,
                actor_user_id=student.user_id,
                event_type=TrainingEventType.LESSON_OPENED,
            )
            await evaluate_regulatory_state(
                db,
                tenant_id=tenant_id,
                enrollment_id=enrollment.id,
            )
            await db.commit()
    return result


@router.get(
    "/lessons/courses/{course_id}/my-progress",
    response_model=CourseProgressDetailResponse,
)
async def guarded_course_progress(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    response = await legacy_lessons.get_course_progress(
        course_id=course_id,
        db=db,
        current_user=current_user,
    )
    tenant_id = get_current_tenant_id()
    profile = await _profile_for_course(db, tenant_id, course_id)
    student = await _student_for_user(db, tenant_id, current_user)
    if not profile or not student:
        return response
    enrollment = await find_active_enrollment(
        db,
        tenant_id=tenant_id,
        student_id=student.id,
        course_id=course_id,
    )
    if not enrollment:
        return response
    evaluation = await evaluate_regulatory_state(
        db,
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
    )
    response.certificate_eligible = evaluation.state in {
        RegulatoryCompletionState.CERTIFICATE_PENDING_SIGNATURE,
        RegulatoryCompletionState.CERTIFIED,
    }
    await db.commit()
    return response


@router.post("/certificates/")
async def guarded_certificate_create(
    cert_data: CertificateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    row = (
        await db.execute(
            select(Enrollment, Class, Course)
            .join(Class, Enrollment.class_id == Class.id)
            .join(Course, Class.course_id == Course.id)
            .where(
                Enrollment.id == cert_data.enrollment_id,
                Enrollment.tenant_id == tenant_id,
                Class.tenant_id == tenant_id,
                Course.tenant_id == tenant_id,
            )
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    enrollment, _class, course = row
    profile = await _profile_for_course(db, tenant_id, course.id)
    if profile is None:
        return await legacy_certificates.create_certificate(
            cert_data=cert_data,
            db=db,
            current_user=current_user,
        )
    evaluation = await evaluate_regulatory_state(
        db,
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
    )
    await db.commit()
    raise HTTPException(
        status_code=409,
        detail={
            "message": "Regulatory certificate issuance is reserved for the signed-document pipeline",
            "state": evaluation.state,
            "blockers": evaluation.blockers,
        },
    )
