import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.certificates import (
    generate_certificate_number,
    generate_validation_code,
)
from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id, get_current_user
from app.core.storage import (
    ALLOWED_MIME_TYPES,
    MAX_UPLOAD_SIZE,
    delete_object,
    generate_material_download_url,
    generate_material_upload_url,
    generate_upload_url,
    generate_watch_url,
    verify_object_exists,
)
from app.core.utils import utc_now
from app.models.certificate import Certificate
from app.models.class_model import Class, ClassStatus
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.lesson import Lesson, LessonContentType, LessonMaterial, LessonProgress
from app.models.student import Student
from app.models.user import User
from app.schemas.lesson import (
    CourseProgressDetailResponse,
    LessonCreate,
    LessonMaterialCreate,
    LessonMaterialResponse,
    LessonProgressCreate,
    LessonProgressResponse,
    LessonReorderRequest,
    LessonResponse,
    LessonUpdate,
    LessonWithProgressResponse,
    MaterialUploadPresignRequest,
    MaterialUploadPresignResponse,
    UploadPresignRequest,
    UploadPresignResponse,
)

router = APIRouter()


# ─── Helpers ───


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


async def _load_course_tenant_filtered(
    db: AsyncSession, course_id: UUID, tenant_id: UUID
) -> Course:
    """Load a course filtered by tenant_id. Returns 404 if not found or cross-tenant."""
    stmt = select(Course).where(
        Course.id == course_id,
        Course.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )
    return course


async def _load_lesson_tenant_filtered(
    db: AsyncSession, lesson_id: UUID, course_id: UUID, tenant_id: UUID
) -> Lesson:
    """Load a lesson filtered by tenant_id and course_id. 404 if not found."""
    stmt = select(Lesson).where(
        Lesson.id == lesson_id,
        Lesson.course_id == course_id,
        Lesson.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )
    return lesson


async def _require_course_access(
    db: AsyncSession,
    course_id: UUID,
    tenant_id: UUID,
    user: dict,
) -> bool:
    """Verifica se o usuário tem acesso ao curso (tenant-filtered)."""
    is_admin = user.get("role") in ("admin", "super_admin")
    if is_admin:
        return True

    student_id = await _get_student_id(db, user.get("user_id"))

    stmt = (
        select(Enrollment)
        .join(Class)
        .where(
            and_(
                Enrollment.student_id == student_id,
                Enrollment.tenant_id == tenant_id,
                Class.course_id == course_id,
                Class.tenant_id == tenant_id,
                Enrollment.status.in_([
                    EnrollmentStatus.CONFIRMADA,
                    EnrollmentStatus.CONCLUIDA,
                ]),
            )
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


def _validate_youtube_url(url: str) -> str:
    """Validate YouTube URL format and return it."""
    patterns = [
        r'^https?://(www\.)?youtube\.com/watch\?v=[\w-]+',
        r'^https?://(www\.)?youtu\.be/[\w-]+',
        r'^https?://(www\.)?youtube\.com/embed/[\w-]+',
        r'^https?://(www\.)?youtube\.com/shorts/[\w-]+',
    ]
    for pat in patterns:
        if re.match(pat, url):
            return url
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Invalid YouTube URL format",
    )


def _validate_vimeo_url(url: str) -> str:
    """Validate Vimeo URL format and return it."""
    patterns = [
        r'^https?://(www\.)?vimeo\.com/\d+',
        r'^https?://(www\.)?player\.vimeo\.com/video/\d+',
    ]
    for pat in patterns:
        if re.match(pat, url):
            return url
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Invalid Vimeo URL format",
    )


def _clean_content_type_switch(
    lesson: Lesson, new_content_type: LessonContentType
) -> None:
    """When switching content types, clean incompatible state safely."""
    if new_content_type == LessonContentType.UPLOAD:
        # Switching TO upload: clear external video URL
        lesson.video_url = None
    elif new_content_type in (LessonContentType.YOUTUBE, LessonContentType.VIMEO):
        # Switching FROM upload: clear storage key (video will come from external URL)
        lesson.storage_key = None


# ─── Lesson CRUD ───


@router.post("/courses/{course_id}/lessons", response_model=LessonResponse, status_code=status.HTTP_201_CREATED)
async def create_lesson(
    course_id: UUID,
    lesson_data: LessonCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _load_course_tenant_filtered(db, course_id, tenant_id)

    # Validate video_url for external content types
    if lesson_data.content_type == LessonContentType.YOUTUBE and lesson_data.video_url:
        _validate_youtube_url(lesson_data.video_url)
    elif lesson_data.content_type == LessonContentType.VIMEO and lesson_data.video_url:
        _validate_vimeo_url(lesson_data.video_url)

    lesson = Lesson(
        tenant_id=tenant_id,
        course_id=course_id,
        title=lesson_data.title,
        description=lesson_data.description,
        order=lesson_data.order,
        content_type=lesson_data.content_type,
        video_url=lesson_data.video_url,
        duration_seconds=lesson_data.duration_seconds,
        is_free_preview=lesson_data.is_free_preview,
        is_required=lesson_data.is_required,
    )
    db.add(lesson)
    await db.commit()
    await db.refresh(lesson)
    return lesson


@router.get("/courses/{course_id}/lessons")
async def list_lessons(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
):
    tenant_id = get_current_tenant_id()
    await _load_course_tenant_filtered(db, course_id, tenant_id)

    has_access = await _require_course_access(db, course_id, tenant_id, current_user)

    stmt = (
        select(Lesson)
        .where(Lesson.course_id == course_id, Lesson.tenant_id == tenant_id)
        .order_by(Lesson.order)
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    lessons = result.scalars().all()

    # For students with access, return lessons with progress
    if has_access and current_user.get("role") == "student":
        student_id = await _get_student_id(db, current_user["user_id"])
        progress_map = {}
        prog_stmt = select(LessonProgress).where(
            LessonProgress.student_id == student_id,
            LessonProgress.tenant_id == tenant_id,
        )
        prog_result = await db.execute(prog_stmt)
        for prog in prog_result.scalars().all():
            progress_map[prog.lesson_id] = prog

        return [
            LessonWithProgressResponse(
                id=lesson.id,
                tenant_id=lesson.tenant_id,
                course_id=lesson.course_id,
                title=lesson.title,
                description=lesson.description,
                order=lesson.order,
                content_type=lesson.content_type,
                video_url=lesson.video_url,
                storage_key=lesson.storage_key,
                duration_seconds=lesson.duration_seconds,
                is_free_preview=lesson.is_free_preview,
                is_required=lesson.is_required,
                created_at=lesson.created_at,
                updated_at=lesson.updated_at,
                watched_seconds=progress_map[lesson.id].watched_seconds if lesson.id in progress_map else 0,
                completed=progress_map[lesson.id].completed if lesson.id in progress_map else False,
                completed_at=progress_map[lesson.id].completed_at if lesson.id in progress_map else None,
            )
            for lesson in lessons
        ]

    # For non-enrolled users, only show free preview lessons with hidden URLs
    if not has_access:
        return [
            LessonResponse(
                id=lesson.id,
                tenant_id=lesson.tenant_id,
                course_id=lesson.course_id,
                title=lesson.title,
                description=lesson.description,
                order=lesson.order,
                content_type=lesson.content_type,
                video_url=None,
                storage_key=None,
                duration_seconds=lesson.duration_seconds,
                is_free_preview=lesson.is_free_preview,
                is_required=lesson.is_required,
                created_at=lesson.created_at,
                updated_at=lesson.updated_at,
            )
            for lesson in lessons
            if lesson.is_free_preview
        ]

    # Admins get full lesson data
    return [LessonResponse.model_validate(lesson) for lesson in lessons]


@router.get("/courses/{course_id}/lessons/{lesson_id}", response_model=LessonResponse)
async def get_lesson(
    course_id: UUID,
    lesson_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    lesson = await _load_lesson_tenant_filtered(db, lesson_id, course_id, tenant_id)

    has_access = await _require_course_access(db, course_id, tenant_id, current_user)
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
    tenant_id = get_current_tenant_id()
    lesson = await _load_lesson_tenant_filtered(db, lesson_id, course_id, tenant_id)

    update_data = lesson_data.model_dump(exclude_unset=True)

    # Handle content type switching
    if "content_type" in update_data:
        new_ct = update_data["content_type"]
        if isinstance(new_ct, str):
            new_ct = LessonContentType(new_ct)
        _clean_content_type_switch(lesson, new_ct)

    # Validate video_url for external content types
    ct = update_data.get("content_type", lesson.content_type)
    if isinstance(ct, str):
        ct = LessonContentType(ct)
    if update_data.get("video_url"):
        if ct == LessonContentType.YOUTUBE:
            _validate_youtube_url(update_data["video_url"])
        elif ct == LessonContentType.VIMEO:
            _validate_vimeo_url(update_data["video_url"])

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
    tenant_id = get_current_tenant_id()
    lesson = await _load_lesson_tenant_filtered(db, lesson_id, course_id, tenant_id)

    # Check if any LessonProgress exists — refuse to destroy learning history
    progress_count = await db.scalar(
        select(func.count(LessonProgress.id)).where(
            LessonProgress.lesson_id == lesson_id,
            LessonProgress.tenant_id == tenant_id,
        )
    )
    if progress_count and progress_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete lesson: student progress exists. "
                   "Archive or remove progress first.",
        )

    # No progress — safe to hard delete
    await db.delete(lesson)
    await db.commit()

    # Normalize ordering for remaining lessons
    await _normalize_lesson_order(db, course_id, tenant_id)


async def _normalize_lesson_order(db: AsyncSession, course_id: UUID, tenant_id: UUID) -> None:
    """Reassign contiguous order values (1..N) to remaining lessons."""
    stmt = (
        select(Lesson)
        .where(Lesson.course_id == course_id, Lesson.tenant_id == tenant_id)
        .order_by(Lesson.order, Lesson.created_at)
    )
    result = await db.execute(stmt)
    lessons = result.scalars().all()
    for idx, lesson in enumerate(lessons, start=1):
        if lesson.order != idx:
            lesson.order = idx
    await db.commit()


# ─── Reorder ───


@router.put("/courses/{course_id}/lessons/reorder", response_model=list[LessonResponse])
async def reorder_lessons(
    course_id: UUID,
    reorder_data: LessonReorderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _load_course_tenant_filtered(db, course_id, tenant_id)

    lesson_ids = reorder_data.lesson_ids

    # Validate: no duplicates
    if len(lesson_ids) != len(set(lesson_ids)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Duplicate lesson IDs in reorder request",
        )

    # Load all lessons for this course+tenant
    stmt = (
        select(Lesson)
        .where(Lesson.course_id == course_id, Lesson.tenant_id == tenant_id)
    )
    result = await db.execute(stmt)
    existing_lessons = result.scalars().all()
    existing_map = {lesson.id: lesson for lesson in existing_lessons}

    # Validate: all IDs belong to this course+tenant
    for lid in lesson_ids:
        if lid not in existing_map:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Lesson {lid} does not belong to this course/tenant",
            )

    # Validate: no missing lessons
    existing_ids = set(existing_map.keys())
    provided_ids = set(lesson_ids)
    missing = existing_ids - provided_ids
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing lesson IDs in reorder request: {missing}",
        )

    # Assign contiguous order 1..N
    for idx, lid in enumerate(lesson_ids, start=1):
        existing_map[lid].order = idx

    await db.commit()

    # Return lessons in new order
    ordered = [existing_map[lid] for lid in lesson_ids]
    return [LessonResponse.model_validate(lesson) for lesson in ordered]


# ─── Video Upload Lifecycle ───


@router.post("/{lesson_id}/upload-presign", response_model=UploadPresignResponse)
async def presign_lesson_upload(
    lesson_id: UUID,
    upload_data: UploadPresignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Step 1: Generate presigned PUT URL for video upload.

    Does NOT replace lesson.storage_key — that only happens after
    upload-complete verification.
    """
    tenant_id = get_current_tenant_id()
    # Load lesson (need course_id for tenant-aware key)
    stmt = select(Lesson).where(
        Lesson.id == lesson_id,
        Lesson.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    # Validate MIME type
    if upload_data.mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Content type not allowed: {upload_data.mime_type}",
        )

    # Validate size
    if upload_data.size_bytes > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum of {MAX_UPLOAD_SIZE} bytes",
        )

    upload_url, storage_key = await generate_upload_url(
        lesson_id=lesson_id,
        filename=upload_data.filename,
        content_type=upload_data.mime_type,
        content_length=upload_data.size_bytes,
        tenant_id=tenant_id,
        course_id=lesson.course_id,
    )

    return UploadPresignResponse(upload_url=upload_url, storage_key=storage_key)


@router.post("/{lesson_id}/upload-complete", response_model=LessonResponse)
async def complete_lesson_upload(
    lesson_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
    storage_key: str = "",
):
    """Step 3: Verify upload completed and activate the new video.

    Only after successful head_object verification does lesson.storage_key
    get updated. If verification fails, the lesson continues pointing to
    the previous valid video.
    """
    tenant_id = get_current_tenant_id()
    stmt = select(Lesson).where(
        Lesson.id == lesson_id,
        Lesson.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    # Verify the object actually exists in storage
    exists = await verify_object_exists(storage_key)
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload verification failed: object not found in storage. "
                   "Lesson video was not changed.",
        )

    # Save the old storage_key for cleanup
    old_storage_key = lesson.storage_key

    # Activate the new video
    lesson.content_type = LessonContentType.UPLOAD
    lesson.storage_key = storage_key
    lesson.video_url = None  # Clear external URL when using upload

    await db.commit()
    await db.refresh(lesson)

    # Best-effort cleanup of old video (after new one is confirmed)
    if old_storage_key and old_storage_key != storage_key:
        await delete_object(old_storage_key)

    return lesson


@router.post("/{lesson_id}/remove-video", response_model=LessonResponse)
async def remove_lesson_video(
    lesson_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Remove the video from a lesson. Does NOT delete LessonProgress."""
    tenant_id = get_current_tenant_id()
    stmt = select(Lesson).where(
        Lesson.id == lesson_id,
        Lesson.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    old_storage_key = lesson.storage_key

    lesson.storage_key = None
    lesson.video_url = None
    # Keep content_type as-is (don't change to UPLOAD if it was YOUTUBE)

    await db.commit()
    await db.refresh(lesson)

    # Best-effort cleanup of old video from storage
    if old_storage_key:
        await delete_object(old_storage_key)

    return lesson


@router.get("/{lesson_id}/watch-url")
async def get_lesson_watch_url(
    lesson_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    stmt = select(Lesson).where(
        Lesson.id == lesson_id,
        Lesson.tenant_id == tenant_id,
    )
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

    # UPLOAD: verify access (except preview)
    if not lesson.is_free_preview:
        has_access = await _require_course_access(db, lesson.course_id, tenant_id, current_user)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this lesson",
            )

    # Use stored storage_key directly; fall back to legacy reconstruction
    if lesson.storage_key:
        watch_url = await generate_watch_url(storage_key=lesson.storage_key)
    else:
        # Legacy: reconstruct key from lesson_id (old records without storage_key)
        # This path is for backward compatibility and should rarely be hit
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not uploaded yet",
        )

    return {"watch_url": watch_url}


# ─── Lesson Progress ───


@router.post("/{lesson_id}/progress", response_model=LessonProgressResponse)
async def update_lesson_progress(
    lesson_id: UUID,
    progress_data: LessonProgressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    stmt = select(Lesson).where(
        Lesson.id == lesson_id,
        Lesson.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    if not lesson.is_free_preview:
        has_access = await _require_course_access(db, lesson.course_id, tenant_id, current_user)
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
        and_(
            LessonProgress.student_id == student_id,
            LessonProgress.lesson_id == lesson_id,
            LessonProgress.tenant_id == tenant_id,
        )
    )
    result = await db.execute(stmt)
    progress = result.scalar_one_or_none()

    if not progress:
        progress = LessonProgress(
            tenant_id=tenant_id,
            student_id=student_id,
            lesson_id=lesson_id,
            watched_seconds=progress_data.watched_seconds,
            completed=False,
        )
        db.add(progress)
    else:
        progress.watched_seconds = max(progress.watched_seconds, progress_data.watched_seconds)

    # Marca como concluído se atingiu 90% da duração ou veio completed=True
    # Only for UPLOAD content type — external videos require manual completion
    if progress_data.completed:
        progress.completed = True
        progress.completed_at = utc_now()
    elif lesson.content_type == LessonContentType.UPLOAD and lesson.duration_seconds:
        if progress.watched_seconds >= int(lesson.duration_seconds * 0.9):
            progress.completed = True
            progress.completed_at = utc_now()

    await db.flush()

    # Gatilho: verifica se todas as aulas obrigatórias do curso foram concluídas
    if progress.completed:
        await _maybe_create_certificate(db, student_id, lesson.course_id, tenant_id)

    await db.commit()
    await db.refresh(progress)
    return progress


@router.get("/courses/{course_id}/my-progress", response_model=CourseProgressDetailResponse)
async def get_course_progress(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    await _load_course_tenant_filtered(db, course_id, tenant_id)

    has_access = await _require_course_access(db, course_id, tenant_id, current_user)
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this course",
        )

    student_id = await _get_student_id(db, current_user.get("user_id"))

    # Count required and optional lessons
    total_stmt = select(func.count(Lesson.id)).where(
        and_(Lesson.course_id == course_id, Lesson.tenant_id == tenant_id)
    )
    total_lessons = await db.scalar(total_stmt) or 0

    required_stmt = select(func.count(Lesson.id)).where(
        and_(Lesson.course_id == course_id, Lesson.tenant_id == tenant_id, Lesson.is_required == True)
    )
    required_lessons = await db.scalar(required_stmt) or 0

    optional_lessons = total_lessons - required_lessons

    # Count completed required lessons
    completed_required_stmt = (
        select(func.count(LessonProgress.id))
        .join(Lesson)
        .where(
            and_(
                LessonProgress.student_id == student_id,
                LessonProgress.tenant_id == tenant_id,
                Lesson.course_id == course_id,
                LessonProgress.completed == True,
                Lesson.is_required == True,
            )
        )
    )
    completed_required = await db.scalar(completed_required_stmt) or 0

    # Count completed optional lessons
    completed_optional_stmt = (
        select(func.count(LessonProgress.id))
        .join(Lesson)
        .where(
            and_(
                LessonProgress.student_id == student_id,
                LessonProgress.tenant_id == tenant_id,
                Lesson.course_id == course_id,
                LessonProgress.completed == True,
                Lesson.is_required == False,
            )
        )
    )
    completed_optional = await db.scalar(completed_optional_stmt) or 0

    percentage = 0.0
    if required_lessons > 0:
        percentage = round((completed_required / required_lessons) * 100, 2)

    certificate_eligible = required_lessons > 0 and completed_required >= required_lessons

    return CourseProgressDetailResponse(
        course_id=course_id,
        total_lessons=total_lessons,
        required_lessons=required_lessons,
        optional_lessons=optional_lessons,
        completed_required=completed_required,
        completed_optional=completed_optional,
        percentage=percentage,
        certificate_eligible=certificate_eligible,
    )


# ─── Materials ───


@router.post("/{lesson_id}/materials/presign", response_model=MaterialUploadPresignResponse)
async def presign_material_upload(
    lesson_id: UUID,
    upload_data: MaterialUploadPresignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Generate presigned URL for material upload."""
    tenant_id = get_current_tenant_id()
    stmt = select(Lesson).where(
        Lesson.id == lesson_id,
        Lesson.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    upload_url, storage_key = await generate_material_upload_url(
        tenant_id=tenant_id,
        course_id=lesson.course_id,
        lesson_id=lesson_id,
        filename=upload_data.filename,
        mime_type=upload_data.mime_type,
        size_bytes=upload_data.size_bytes,
    )

    return MaterialUploadPresignResponse(upload_url=upload_url, storage_key=storage_key)


@router.post("/{lesson_id}/materials", response_model=LessonMaterialResponse, status_code=status.HTTP_201_CREATED)
async def create_lesson_material(
    lesson_id: UUID,
    material_data: LessonMaterialCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
    storage_key: str | None = None,
    mime_type: str | None = None,
    size_bytes: int | None = None,
):
    tenant_id = get_current_tenant_id()
    stmt = select(Lesson).where(
        Lesson.id == lesson_id,
        Lesson.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    material = LessonMaterial(
        tenant_id=tenant_id,
        lesson_id=lesson_id,
        title=material_data.title,
        file_url=material_data.file_url,
        storage_key=storage_key,
        mime_type=mime_type,
        size_bytes=size_bytes,
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
    tenant_id = get_current_tenant_id()
    stmt = select(Lesson).where(
        Lesson.id == lesson_id,
        Lesson.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    if not lesson.is_free_preview:
        has_access = await _require_course_access(db, lesson.course_id, tenant_id, current_user)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this lesson",
            )

    stmt = select(LessonMaterial).where(
        LessonMaterial.lesson_id == lesson_id,
        LessonMaterial.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    materials = result.scalars().all()
    return materials


@router.get("/{lesson_id}/materials/{material_id}/download")
async def download_lesson_material(
    lesson_id: UUID,
    material_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Generate a download URL for a material file."""
    tenant_id = get_current_tenant_id()
    stmt = select(LessonMaterial).where(
        LessonMaterial.id == material_id,
        LessonMaterial.lesson_id == lesson_id,
        LessonMaterial.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found",
        )

    # Check access (except free preview lessons)
    lesson_stmt = select(Lesson).where(
        Lesson.id == lesson_id,
        Lesson.tenant_id == tenant_id,
    )
    lesson_result = await db.execute(lesson_stmt)
    lesson = lesson_result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    if not lesson.is_free_preview:
        has_access = await _require_course_access(db, lesson.course_id, tenant_id, current_user)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this lesson",
            )

    # Prefer storage_key-based download URL; fall back to legacy file_url
    if material.storage_key:
        download_url = await generate_material_download_url(material.storage_key)
        return {"download_url": download_url}
    elif material.file_url:
        return {"download_url": material.file_url}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material file not available",
        )


@router.delete("/{lesson_id}/materials/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lesson_material(
    lesson_id: UUID,
    material_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(LessonMaterial).where(
        LessonMaterial.id == material_id,
        LessonMaterial.lesson_id == lesson_id,
        LessonMaterial.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found",
        )

    # Best-effort cleanup of storage object
    if material.storage_key:
        await delete_object(material.storage_key)

    await db.delete(material)
    await db.commit()


# ─── Admin Course Progress ───


@router.get("/courses/{course_id}/progress", response_model=list[dict])
async def get_course_student_progress(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Admin view: per-student progress for a course."""
    tenant_id = get_current_tenant_id()
    await _load_course_tenant_filtered(db, course_id, tenant_id)

    # Find all enrollments for this course's classes
    stmt = (
        select(Enrollment, Student, Class, User)
        .join(Student, Enrollment.student_id == Student.id)
        .join(Class, Enrollment.class_id == Class.id)
        .join(User, Student.user_id == User.id)
        .where(
            and_(
                Class.course_id == course_id,
                Class.tenant_id == tenant_id,
                Enrollment.tenant_id == tenant_id,
            )
        )
    )
    result = await db.execute(stmt)
    rows = result.all()

    # Count required lessons
    required_count = await db.scalar(
        select(func.count(Lesson.id)).where(
            and_(Lesson.course_id == course_id, Lesson.tenant_id == tenant_id, Lesson.is_required == True)
        )
    ) or 0

    progress_list = []
    for enrollment, student, cls, user in rows:
        # Count completed required lessons for this student
        completed_required = await db.scalar(
            select(func.count(LessonProgress.id))
            .join(Lesson)
            .where(
                and_(
                    LessonProgress.student_id == student.id,
                    LessonProgress.tenant_id == tenant_id,
                    Lesson.course_id == course_id,
                    LessonProgress.completed == True,
                    Lesson.is_required == True,
                )
            )
        ) or 0

        # Check certificate
        cert_count = await db.scalar(
            select(func.count(Certificate.id)).where(
                Certificate.enrollment_id == enrollment.id,
                Certificate.tenant_id == tenant_id,
            )
        ) or 0

        percentage = round((completed_required / required_count) * 100, 2) if required_count > 0 else 0.0

        progress_list.append({
            "student_id": str(student.id),
            "student_name": user.full_name,
            "class_name": f"Turma {cls.start_date.strftime('%m/%Y')}" if cls.start_date else "N/A",
            "enrollment_status": enrollment.status.value if hasattr(enrollment.status, 'value') else str(enrollment.status),
            "required_completed": completed_required,
            "required_total": required_count,
            "percentage": percentage,
            "certificate_status": "Sim" if cert_count > 0 else "Não",
        })

    return progress_list


# ─── Certificate Auto-Generation ───


async def _maybe_create_certificate(
    db: AsyncSession, student_id: UUID, course_id: UUID, tenant_id: UUID
):
    """Cria certificado e conclui a matrícula correta se todas as aulas
    obrigatórias (is_required=True) estiverem concluídas.

    Idempotent: uses on_conflict_do_nothing on enrollment_id.
    """
    # Count required lessons
    total_stmt = select(func.count(Lesson.id)).where(
        and_(
            Lesson.course_id == course_id,
            Lesson.tenant_id == tenant_id,
            Lesson.is_required == True,
        )
    )
    total_result = await db.execute(total_stmt)
    total_lessons = total_result.scalar() or 0

    completed_stmt = (
        select(func.count(LessonProgress.id))
        .join(Lesson)
        .where(
            and_(
                LessonProgress.student_id == student_id,
                LessonProgress.tenant_id == tenant_id,
                Lesson.course_id == course_id,
                LessonProgress.completed == True,
                Lesson.is_required == True,
            )
        )
    )
    completed_result = await db.execute(completed_stmt)
    completed_lessons = completed_result.scalar() or 0

    if total_lessons == 0 or completed_lessons < total_lessons:
        return

    # Seleciona a matrícula correta do fluxo: ativa (CONFIRMADA),
    # em turma EM_ANDAMENTO, preferindo a turma mais recente.
    stmt = (
        select(Enrollment)
        .join(Class)
        .where(
            and_(
                Enrollment.student_id == student_id,
                Enrollment.tenant_id == tenant_id,
                Class.course_id == course_id,
                Class.tenant_id == tenant_id,
                Enrollment.status.in_([
                    EnrollmentStatus.CONFIRMADA,
                    EnrollmentStatus.CONCLUIDA,
                ]),
            )
        )
        .order_by(
            # Prefer CONFIRMADA over CONCLUIDA
            (Enrollment.status == EnrollmentStatus.CONFIRMADA).desc(),
            # Prefer EM_ANDAMENTO classes
            (Class.status == ClassStatus.EM_ANDAMENTO).desc(),
            (Class.status == ClassStatus.ABERTA).desc(),
            Class.start_date.desc(),
            Enrollment.enrollment_date.desc(),
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    enrollment = result.scalar_one_or_none()

    if not enrollment:
        return

    cert_stmt = (
        insert(Certificate)
        .values(
            enrollment_id=enrollment.id,
            certificate_number=generate_certificate_number(),
            validation_code=generate_validation_code(),
            tenant_id=tenant_id,
        )
        .on_conflict_do_nothing(index_elements=["enrollment_id"])
    )

    try:
        await db.execute(cert_stmt)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao emitir certificado",
        )

    enrollment.status = EnrollmentStatus.CONCLUIDA
