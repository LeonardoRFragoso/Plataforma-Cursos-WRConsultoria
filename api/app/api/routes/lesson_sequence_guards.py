"""Sequential lesson access guards for the student learning journey.

A student may access lesson N only after the immediately previous lesson in
course order has a completed LessonProgress record. Uploaded lessons only
become complete after an explicit finish signal near the actual end of the
video. Admin and super-admin behavior is delegated unchanged.

This module prepends guarded route handlers to the existing lessons and
assessments routers so direct API calls cannot bypass the UI lock.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes import assessments, lessons
from app.core.database import get_db
from app.core.security import get_current_tenant_id, get_current_user
from app.core.utils import utc_now
from app.models.lesson import Lesson, LessonContentType, LessonProgress
from app.schemas.lesson import LessonProgressCreate, LessonProgressResponse
from app.services.assessment_service import course_requires_assessment


lessons_guard_router = APIRouter()
assessments_guard_router = APIRouter()


async def _require_previous_lesson_completed(
    db: AsyncSession,
    *,
    lesson: Lesson,
    student_id: UUID,
    tenant_id: UUID,
) -> None:
    """Raise 409 when the immediately previous lesson is not completed."""
    previous_lesson = (
        await db.execute(
            select(Lesson)
            .where(
                Lesson.tenant_id == tenant_id,
                Lesson.course_id == lesson.course_id,
                Lesson.order < lesson.order,
            )
            .order_by(Lesson.order.desc(), Lesson.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if previous_lesson is None:
        return

    previous_completed = (
        await db.execute(
            select(LessonProgress.id).where(
                LessonProgress.tenant_id == tenant_id,
                LessonProgress.student_id == student_id,
                LessonProgress.lesson_id == previous_lesson.id,
                LessonProgress.completed.is_(True),
            )
        )
    ).scalar_one_or_none()

    if previous_completed is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Conclua a aula {previous_lesson.order} antes de acessar "
                f"a aula {lesson.order}."
            ),
        )


async def _load_student_lesson_context(
    db: AsyncSession,
    *,
    lesson_id: UUID,
    tenant_id: UUID,
    current_user: dict,
) -> tuple[Lesson, UUID]:
    lesson = (
        await db.execute(
            select(Lesson).where(
                Lesson.id == lesson_id,
                Lesson.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if lesson is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    student_id = await lessons._get_student_id(db, current_user.get("user_id"))
    await _require_previous_lesson_completed(
        db,
        lesson=lesson,
        student_id=student_id,
        tenant_id=tenant_id,
    )
    return lesson, student_id


async def _persist_guarded_student_progress(
    db: AsyncSession,
    *,
    lesson: Lesson,
    student_id: UUID,
    tenant_id: UUID,
    progress_data: LessonProgressCreate,
    assessment_mode: bool,
) -> LessonProgress:
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
                LessonProgress.student_id == student_id,
                LessonProgress.lesson_id == lesson.id,
                LessonProgress.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()

    if progress is None:
        progress = LessonProgress(
            tenant_id=tenant_id,
            student_id=student_id,
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

    if progress_data.completed and not progress.completed:
        if lesson.content_type == LessonContentType.UPLOAD and lesson.duration_seconds:
            minimum_finish_seconds = max(1, int(lesson.duration_seconds * 0.98))
            if progress.watched_seconds < minimum_finish_seconds:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Assista a aula até o final antes de marcá-la como concluída.",
                )
        progress.completed = True
        progress.completed_at = utc_now()

    await db.flush()

    if progress.completed and not assessment_mode:
        await lessons._maybe_create_certificate(
            db,
            student_id,
            lesson.course_id,
            tenant_id,
        )

    await db.commit()
    await db.refresh(progress)
    return progress


@lessons_guard_router.get("/{lesson_id}/watch-url")
async def guarded_watch_url(
    lesson_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Block playback of a later lesson until the previous one is complete."""
    if current_user.get("role") != "student":
        return await lessons.get_lesson_watch_url(
            lesson_id=lesson_id,
            db=db,
            current_user=current_user,
        )

    tenant_id = get_current_tenant_id()
    lesson, _student_id = await _load_student_lesson_context(
        db,
        lesson_id=lesson_id,
        tenant_id=tenant_id,
        current_user=current_user,
    )

    return await lessons.get_lesson_watch_url(
        lesson_id=lesson.id,
        db=db,
        current_user=current_user,
    )


@lessons_guard_router.post(
    "/{lesson_id}/progress",
    response_model=LessonProgressResponse,
)
async def guarded_legacy_progress(
    lesson_id: UUID,
    progress_data: LessonProgressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Persist progress without auto-completing uploaded lessons at 90%."""
    if current_user.get("role") != "student":
        return await lessons.update_lesson_progress(
            lesson_id=lesson_id,
            progress_data=progress_data,
            db=db,
            current_user=current_user,
        )

    tenant_id = get_current_tenant_id()
    lesson, student_id = await _load_student_lesson_context(
        db,
        lesson_id=lesson_id,
        tenant_id=tenant_id,
        current_user=current_user,
    )

    if not lesson.is_free_preview:
        has_access = await lessons._require_course_access(
            db,
            lesson.course_id,
            tenant_id,
            current_user,
        )
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this lesson",
            )

    return await _persist_guarded_student_progress(
        db,
        lesson=lesson,
        student_id=student_id,
        tenant_id=tenant_id,
        progress_data=progress_data,
        assessment_mode=False,
    )


@assessments_guard_router.post(
    "/lessons/{lesson_id}/progress",
    response_model=LessonProgressResponse,
)
async def guarded_assessment_progress(
    lesson_id: UUID,
    progress_data: LessonProgressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Apply strict finish + sequence rules to NR assessment courses."""
    if current_user.get("role") != "student":
        return await assessments.assessment_lesson_progress(
            lesson_id=lesson_id,
            progress_data=progress_data,
            db=db,
            current_user=current_user,
        )

    tenant_id = get_current_tenant_id()
    lesson, student_id = await _load_student_lesson_context(
        db,
        lesson_id=lesson_id,
        tenant_id=tenant_id,
        current_user=current_user,
    )

    course = await assessments._load_course(db, lesson.course_id, tenant_id)
    if not course_requires_assessment(course.code):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment progress route is not configured for this course",
        )

    student = await assessments._load_student(db, tenant_id, current_user)
    await assessments._load_enrollment(
        db,
        student_id=student.id,
        course_id=course.id,
        tenant_id=tenant_id,
    )

    return await _persist_guarded_student_progress(
        db,
        lesson=lesson,
        student_id=student_id,
        tenant_id=tenant_id,
        progress_data=progress_data,
        assessment_mode=True,
    )


for _route in reversed(lessons_guard_router.routes):
    lessons.router.routes.insert(0, _route)

for _route in reversed(assessments_guard_router.routes):
    assessments.router.routes.insert(0, _route)
