"""Canonical academic progress calculation.

Single source of truth for course progress percentage, shared by:
- ``GET /courses/{course_id}/my-progress`` (student-facing)
- ``GET /api/v1/b2b/...`` (B2B read-only API)

The canonical rule is **required-only**:
    progress = completed_required / required_lessons * 100

Optional lessons do NOT count toward progress or certificate eligibility.
This matches the pedagogical requirement that only mandatory lessons
must be completed to earn a certificate.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lesson import Lesson, LessonProgress


@dataclass(frozen=True)
class CourseProgress:
    """Canonical progress result for a single student in a single course."""

    total_lessons: int
    required_lessons: int
    optional_lessons: int
    completed_required: int
    completed_optional: int
    percentage: float
    certificate_eligible: bool


async def compute_course_progress(
    db: AsyncSession,
    tenant_id,
    course_id,
    student_id: str | None = None,
) -> CourseProgress:
    """Compute canonical required-only progress for a student in a course.

    If ``student_id`` is None, completed counts are 0 (useful for
    computing course-level aggregate stats where no specific student
    is being queried).

    Returns a ``CourseProgress`` dataclass with all fields populated.
    ``percentage`` is in [0, 100] and rounded to 1 decimal place.
    ``certificate_eligible`` is True only when ``required_lessons > 0``
    and ``completed_required >= required_lessons``.
    """
    total_lessons = int(await db.scalar(
        select(func.count(Lesson.id)).where(
            Lesson.tenant_id == tenant_id,
            Lesson.course_id == course_id,
        )
    ) or 0)

    required_lessons = int(await db.scalar(
        select(func.count(Lesson.id)).where(
            Lesson.tenant_id == tenant_id,
            Lesson.course_id == course_id,
            Lesson.is_required.is_(True),
        )
    ) or 0)

    optional_lessons = total_lessons - required_lessons

    if student_id is not None:
        completed_required = int(await db.scalar(
            select(func.count(LessonProgress.id))
            .join(Lesson, Lesson.id == LessonProgress.lesson_id)
            .where(
                LessonProgress.tenant_id == tenant_id,
                LessonProgress.student_id == student_id,
                Lesson.course_id == course_id,
                LessonProgress.completed.is_(True),
                Lesson.is_required.is_(True),
            )
        ) or 0)

        completed_optional = int(await db.scalar(
            select(func.count(LessonProgress.id))
            .join(Lesson, Lesson.id == LessonProgress.lesson_id)
            .where(
                LessonProgress.tenant_id == tenant_id,
                LessonProgress.student_id == student_id,
                Lesson.course_id == course_id,
                LessonProgress.completed.is_(True),
                Lesson.is_required.is_(False),
            )
        ) or 0)
    else:
        completed_required = 0
        completed_optional = 0

    percentage = (
        round((completed_required / required_lessons) * 100, 1)
        if required_lessons > 0
        else 0.0
    )
    certificate_eligible = (
        required_lessons > 0 and completed_required >= required_lessons
    )

    return CourseProgress(
        total_lessons=total_lessons,
        required_lessons=required_lessons,
        optional_lessons=optional_lessons,
        completed_required=completed_required,
        completed_optional=completed_optional,
        percentage=percentage,
        certificate_eligible=certificate_eligible,
    )


async def compute_progress_percentage(
    db: AsyncSession,
    tenant_id,
    course_id,
    student_id,
) -> float:
    """Convenience: return only the percentage (0-100, required-only)."""
    result = await compute_course_progress(db, tenant_id, course_id, student_id)
    return result.percentage
