from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lesson import Lesson, LessonContentType, LessonProgress


UPLOAD_COMPLETION_THRESHOLD = 0.98


async def require_previous_lesson_completed(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    student_id: UUID,
    lesson: Lesson,
) -> None:
    """Enforce strict sequential learning for a student.

    The immediately preceding lesson in course order must be marked completed
    before a later lesson can be opened or receive progress. This is enforced
    by the API, not only by the UI.
    """
    previous = (
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
    if not previous:
        return

    completed = (
        await db.execute(
            select(LessonProgress).where(
                LessonProgress.tenant_id == tenant_id,
                LessonProgress.student_id == student_id,
                LessonProgress.lesson_id == previous.id,
                LessonProgress.completed.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conclua a aula anterior antes de avançar para esta aula",
        )


def completion_allowed(
    *,
    lesson: Lesson,
    requested_completed: bool,
    watched_seconds: int,
) -> bool:
    """Return whether this progress update is allowed to complete the lesson.

    Uploaded video lessons require an explicit completion signal (normally the
    HTML video `ended` event) and at least 98% of the registered duration. This
    removes the legacy 90% auto-completion path that could unlock the next
    lesson early. Non-upload content retains explicit completion semantics.
    """
    if not requested_completed:
        return False
    if lesson.content_type != LessonContentType.UPLOAD:
        return True
    if not lesson.duration_seconds:
        return True
    return watched_seconds >= int(lesson.duration_seconds * UPLOAD_COMPLETION_THRESHOLD)
