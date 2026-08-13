from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.certificates import (
    generate_certificate_number,
    generate_validation_code,
)
from app.core.database import get_db
from app.core.security import get_current_admin, get_current_user
from app.core.storage import generate_upload_url, generate_watch_url
from app.core.utils import utc_now
from app.models.certificate import Certificate
from app.models.class_model import Class
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.lesson import Lesson, LessonContentType, LessonMaterial, LessonProgress
from app.models.student import Student
from app.schemas.lesson import (
    CourseProgressResponse,
    LessonCreate,
    LessonMaterialCreate,
    LessonMaterialResponse,
    LessonProgressCreate,
    LessonProgressResponse,
    LessonResponse,
    LessonUpdate,
)

router = APIRouter()


async def _get_student_id(db: AsyncSession, user_id: str) -> UUID:
    """Busca o Student vinculado ao usuário logado."""
    stmt = select(Student).where(Student.user_id == UUID(user_id))
    result = await db.execute(stmt)
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found",
        )

    return student.id


async def _require_course_access(
    db: AsyncSession,
    course_id: UUID,
    user: dict,
) -> bool:
    """Verifica se o usuário tem acesso ao curso."""
    # Admin sempre tem acesso
    if user.get("role") == "admin":
        return True

    student_id = await _get_student_id(db, user.get("user_id"))

    # Verifica matrícula confirmada/concluída em alguma turma do curso
    stmt = (
        select(Enrollment)
        .join(Class)
        .where(
            and_(
                Enrollment.student_id == student_id,
                Class.course_id == course_id,
                Enrollment.status.in_([
                    EnrollmentStatus.CONFIRMADA,
                    EnrollmentStatus.CONCLUIDA,
                ]),
            )
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


@router.post("/courses/{course_id}/lessons", response_model=LessonResponse, status_code=status.HTTP_201_CREATED)
async def create_lesson(
    course_id: UUID,
    lesson_data: LessonCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    stmt = select(Course).where(Course.id == course_id)
    result = await db.execute(stmt)
    course = result.scalar_one_or_none()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )

    lesson = Lesson(course_id=course_id, **lesson_data.model_dump(exclude={"course_id"}))
    db.add(lesson)
    await db.commit()
    await db.refresh(lesson)
    return lesson


@router.get("/courses/{course_id}/lessons", response_model=list[LessonResponse])
async def list_lessons(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
):
    has_access = await _require_course_access(db, course_id, current_user)

    stmt = select(Lesson).where(Lesson.course_id == course_id).order_by(Lesson.order).offset(skip).limit(limit)
    result = await db.execute(stmt)
    lessons = result.scalars().all()

    # Se não tem acesso, esconde URLs de vídeo e storage
    if not has_access:
        return [
            LessonResponse(
                **{
                    **lesson.__dict__,
                    "video_url": None,
                    "storage_key": None,
                }
            )
            for lesson in lessons
            if lesson.is_free_preview
        ]

    return lessons


@router.get("/courses/{course_id}/lessons/{lesson_id}", response_model=LessonResponse)
async def get_lesson(
    course_id: UUID,
    lesson_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    stmt = select(Lesson).where(and_(Lesson.id == lesson_id, Lesson.course_id == course_id))
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()

    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    has_access = await _require_course_access(db, course_id, current_user)
    if not has_access and not lesson.is_free_preview:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this lesson",
        )

    return lesson


@router.put("/courses/{course_id}/lessons/{lesson_id}", response_model=LessonResponse)
async def update_lesson(
    course_id: UUID,
    lesson_id: UUID,
    lesson_data: LessonUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    stmt = select(Lesson).where(and_(Lesson.id == lesson_id, Lesson.course_id == course_id))
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()

    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    update_data = lesson_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lesson, field, value)

    await db.commit()
    await db.refresh(lesson)
    return lesson


@router.delete("/courses/{course_id}/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lesson(
    course_id: UUID,
    lesson_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    stmt = select(Lesson).where(and_(Lesson.id == lesson_id, Lesson.course_id == course_id))
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()

    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    await db.delete(lesson)
    await db.commit()


@router.post("/{lesson_id}/upload-url")
async def generate_lesson_upload_url(
    lesson_id: UUID,
    filename: str,
    content_type: str = "video/mp4",
    content_length: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    stmt = select(Lesson).where(Lesson.id == lesson_id)
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()

    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    upload_url, storage_key = await generate_upload_url(
        lesson_id=lesson_id,
        filename=filename,
        content_type=content_type,
        content_length=content_length,
    )

    lesson.content_type = LessonContentType.UPLOAD
    lesson.storage_key = storage_key
    await db.commit()

    return {
        "upload_url": upload_url,
        "storage_key": storage_key,
    }


@router.get("/{lesson_id}/watch-url")
async def get_lesson_watch_url(
    lesson_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    stmt = select(Lesson).where(Lesson.id == lesson_id)
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()

    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    if lesson.content_type == LessonContentType.YOUTUBE:
        return {"watch_url": lesson.video_url}

    if lesson.content_type == LessonContentType.VIMEO:
        return {"watch_url": lesson.video_url}

    # UPLOAD: verifica acesso (exceto preview)
    if not lesson.is_free_preview:
        has_access = await _require_course_access(db, lesson.course_id, current_user)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this lesson",
            )

    if not lesson.storage_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not uploaded yet",
        )

    filename = lesson.storage_key.split("/")[-1]
    watch_url = await generate_watch_url(
        lesson_id=lesson_id,
        filename=filename,
    )

    return {"watch_url": watch_url}


@router.post("/{lesson_id}/progress", response_model=LessonProgressResponse)
async def update_lesson_progress(
    lesson_id: UUID,
    progress_data: LessonProgressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    stmt = select(Lesson).where(Lesson.id == lesson_id)
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()

    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    if not lesson.is_free_preview:
        has_access = await _require_course_access(db, lesson.course_id, current_user)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this lesson",
            )

    if progress_data.watched_seconds < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="watched_seconds must be non-negative",
        )

    if lesson.duration_seconds is not None and progress_data.watched_seconds > lesson.duration_seconds:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="watched_seconds cannot exceed lesson duration",
        )

    student_id = await _get_student_id(db, current_user.get("user_id"))

    stmt = select(LessonProgress).where(
        and_(LessonProgress.student_id == student_id, LessonProgress.lesson_id == lesson_id)
    )
    result = await db.execute(stmt)
    progress = result.scalar_one_or_none()

    if not progress:
        progress = LessonProgress(
            student_id=student_id,
            lesson_id=lesson_id,
            watched_seconds=progress_data.watched_seconds,
            completed=False,
        )
        db.add(progress)
    else:
        progress.watched_seconds = max(progress.watched_seconds, progress_data.watched_seconds)

    # Marca como concluído se atingiu 90% da duração ou veio completed=True
    if progress_data.completed or lesson.duration_seconds and progress.watched_seconds >= int(lesson.duration_seconds * 0.9):
        progress.completed = True
        progress.completed_at = utc_now()

    await db.flush()

    # Gatilho: verifica se todas as aulas obrigatórias do curso foram concluídas
    if progress.completed:
        await _maybe_create_certificate(db, student_id, lesson.course_id)

    await db.commit()
    await db.refresh(progress)
    return progress


@router.get("/courses/{course_id}/my-progress", response_model=CourseProgressResponse)
async def get_course_progress(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    has_access = await _require_course_access(db, course_id, current_user)
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this course",
        )

    student_id = await _get_student_id(db, current_user.get("user_id"))

    total_stmt = select(func.count(Lesson.id)).where(
        and_(Lesson.course_id == course_id, Lesson.is_free_preview == False)
    )
    total_result = await db.execute(total_stmt)
    total_lessons = total_result.scalar() or 0

    completed_stmt = (
        select(func.count(LessonProgress.id))
        .join(Lesson)
        .where(
            and_(
                LessonProgress.student_id == student_id,
                Lesson.course_id == course_id,
                LessonProgress.completed == True,
                Lesson.is_free_preview == False,
            )
        )
    )
    completed_result = await db.execute(completed_stmt)
    completed_lessons = completed_result.scalar() or 0

    percentage = 0.0
    if total_lessons > 0:
        percentage = round((completed_lessons / total_lessons) * 100, 2)

    return CourseProgressResponse(
        course_id=course_id,
        total_lessons=total_lessons,
        completed_lessons=completed_lessons,
        percentage=percentage,
    )


# Materiais de apoio

@router.post("/{lesson_id}/materials", response_model=LessonMaterialResponse, status_code=status.HTTP_201_CREATED)
async def create_lesson_material(
    lesson_id: UUID,
    material_data: LessonMaterialCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    stmt = select(Lesson).where(Lesson.id == lesson_id)
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()

    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    material = LessonMaterial(
        lesson_id=lesson_id,
        title=material_data.title,
        file_url=material_data.file_url,
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)
    return material


@router.get("/{lesson_id}/materials", response_model=list[LessonMaterialResponse])
async def list_lesson_materials(
    lesson_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    stmt = select(Lesson).where(Lesson.id == lesson_id)
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()

    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    if not lesson.is_free_preview:
        has_access = await _require_course_access(db, lesson.course_id, current_user)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this lesson",
            )

    stmt = select(LessonMaterial).where(LessonMaterial.lesson_id == lesson_id)
    result = await db.execute(stmt)
    materials = result.scalars().all()
    return materials


async def _maybe_create_certificate(db: AsyncSession, student_id: UUID, course_id: UUID):
    """Cria certificado se todas as aulas obrigatórias do curso estiverem concluídas."""
    total_stmt = select(func.count(Lesson.id)).where(
        and_(Lesson.course_id == course_id, Lesson.is_free_preview == False)
    )
    total_result = await db.execute(total_stmt)
    total_lessons = total_result.scalar() or 0

    completed_stmt = (
        select(func.count(LessonProgress.id))
        .join(Lesson)
        .where(
            and_(
                LessonProgress.student_id == student_id,
                Lesson.course_id == course_id,
                LessonProgress.completed == True,
                Lesson.is_free_preview == False,
            )
        )
    )
    completed_result = await db.execute(completed_stmt)
    completed_lessons = completed_result.scalar() or 0

    if total_lessons == 0 or completed_lessons < total_lessons:
        return

    # Buscar matrículas confirmadas/concluídas do aluno em turmas do curso
    stmt = (
        select(Enrollment)
        .join(Class)
        .where(
            and_(
                Enrollment.student_id == student_id,
                Class.course_id == course_id,
                Enrollment.status.in_([
                    EnrollmentStatus.CONFIRMADA,
                    EnrollmentStatus.CONCLUIDA,
                ]),
            )
        )
    )
    result = await db.execute(stmt)
    enrollments = result.scalars().all()

    for enrollment in enrollments:
        enrollment.status = EnrollmentStatus.CONCLUIDA

        stmt = (
            insert(Certificate)
            .values(
                enrollment_id=enrollment.id,
                certificate_number=generate_certificate_number(),
                validation_code=generate_validation_code(),
            )
            .on_conflict_do_nothing(index_elements=["enrollment_id"])
        )
        await db.execute(stmt)
