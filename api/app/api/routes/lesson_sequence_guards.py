"""Sequential lesson access guards for the student learning journey.

A student may access lesson N only after the immediately previous lesson in
course order has a completed LessonProgress record. The first lesson remains
available. Admin and super-admin behavior is delegated unchanged to the
existing lesson routes.

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
from app.models.lesson import Lesson, LessonProgress
from app.schemas.lesson import LessonProgressCreate, LessonProgressResponse


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

    # Preserve the original access-control checks as the authoritative
    # enrollment/storage policy after the sequential prerequisite passes.
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
    """Prevent direct progress/completion writes to a locked lesson."""
    if current_user.get("role") == "student":
        tenant_id = get_current_tenant_id()
        await _load_student_lesson_context(
            db,
            lesson_id=lesson_id,
            tenant_id=tenant_id,
            current_user=current_user,
        )

    return await lessons.update_lesson_progress(
        lesson_id=lesson_id,
        progress_data=progress_data,
        db=db,
        current_user=current_user,
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
    """Apply the same sequence rule to NR assessment-course progress writes."""
    if current_user.get("role") == "student":
        tenant_id = get_current_tenant_id()
        await _load_student_lesson_context(
            db,
            lesson_id=lesson_id,
            tenant_id=tenant_id,
            current_user=current_user,
        )

    return await assessments.assessment_lesson_progress(
        lesson_id=lesson_id,
        progress_data=progress_data,
        db=db,
        current_user=current_user,
    )


# FastAPI resolves matching routes in registration order. Prepending these
# guarded handlers makes the sequence rule authoritative while keeping the
# existing route implementations as the source of enrollment, storage,
# progress and certificate behavior.
for _route in reversed(lessons_guard_router.routes):
    lessons.router.routes.insert(0, _route)

for _route in reversed(assessments_guard_router.routes):
    assessments.router.routes.insert(0, _route)
