import re
from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.certificates import (
    _content_hash,
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
from app.models.certificate import Certificate, CertificateEvent
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
from app.services.progress_service import compute_course_progress

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
        lesson.video_url = None
    elif new_content_type in (LessonContentType.YOUTUBE, LessonContentType.VIMEO):
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

    if "content_type" in update_data:
        new_ct = update_data["content_type"]
        if isinstance(new_ct, str):
            new_ct = LessonContentType(new_ct)
        _clean_content_type_switch(lesson, new_ct)

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

    await db.delete(lesson)
    await db.commit()
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
    if len(lesson_ids) != len(set(lesson_ids)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Duplicate lesson IDs in reorder request",
        )

    stmt = (
        select(Lesson)
        .where(Lesson.course_id == course_id, Lesson.tenant_id == tenant_id)
    )
    result = await db.execute(stmt)
    existing_lessons = result.scalars().all()
    existing_map = {lesson.id: lesson for lesson in existing_lessons}

    for lid in lesson_ids:
        if lid not in existing_map:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Lesson {lid} does not belong to this course/tenant",
            )

    existing_ids = set(existing_map.keys())
    provided_ids = set(lesson_ids)
    missing = existing_ids - provided_ids
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing lesson IDs in reorder request: {missing}",
        )

    for idx, lid in enumerate(lesson_ids, start=1):
        existing_map[lid].order = idx

    await db.commit()
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
    """Step 1: Generate presigned PUT URL for video upload."""
    tenant_id = get_current_tenant_id()
    stmt = select(Lesson).where(
        Lesson.id == lesson_id,
        Lesson.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    if upload_data.mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Content type not allowed: {upload_data.mime_type}",
        )
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
    tenant_id = get_current_tenant_id()
    stmt = select(Lesson).where(Lesson.id == lesson_id, Lesson.tenant_id == tenant_id)
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    exists = await verify_object_exists(storage_key)
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload verification failed: object not found in storage. Lesson video was not changed.",
        )

    old_storage_key = lesson.storage_key
    lesson.content_type = LessonContentType.UPLOAD
    lesson.storage_key = storage_key
    lesson.video_url = None
    await db.commit()
    await db.refresh(lesson)
    if old_storage_key and old_storage_key != storage_key:
        await delete_object(old_storage_key)
    return lesson


@router.post("/{lesson_id}/remove-video", response_model=LessonResponse)
async def remove_lesson_video(
    lesson_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(Lesson).where(Lesson.id == lesson_id, Lesson.tenant_id == tenant_id)
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    old_storage_key = lesson.storage_key
    lesson.storage_key = None
    lesson.video_url = None
    await db.commit()
    await db.refresh(lesson)
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
    stmt = select(Lesson).where(Lesson.id == lesson_id, Lesson.tenant_id == tenant_id)
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    if lesson.content_type == LessonContentType.YOUTUBE:
        return {"watch_url": lesson.video_url}
    if lesson.content_type == LessonContentType.VIMEO:
        return {"watch_url": lesson.video_url}

    if not lesson.is_free_preview:
        has_access = await _require_course_access(db, lesson.course_id, tenant_id, current_user)
        if not has_access:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this lesson")

    if lesson.storage_key:
        watch_url = await generate_watch_url(storage_key=lesson.storage_key)
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not uploaded yet")
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
    stmt = select(Lesson).where(Lesson.id == lesson_id, Lesson.tenant_id == tenant_id)
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    if not lesson.is_free_preview:
        has_access = await _require_course_access(db, lesson.course_id, tenant_id, current_user)
        if not has_access:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this lesson")

    if progress_data.watched_seconds < 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="watched_seconds must be non-negative")
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

    if progress_data.completed:
        progress.completed = True
        progress.completed_at = utc_now()
    elif lesson.content_type == LessonContentType.UPLOAD and lesson.duration_seconds:
        if progress.watched_seconds >= int(lesson.duration_seconds * 0.9):
            progress.completed = True
            progress.completed_at = utc_now()

    await db.flush()
    completed_enrollment = None
    certificate_id = None
    if progress.completed:
        completed_enrollment, certificate_id = await _maybe_create_certificate(
            db, student_id, lesson.course_id, tenant_id
        )

    await db.commit()

    # Send notifications AFTER commit — emails are best-effort side effects
    # and must never roll back the completed enrollment/certificate.
    if completed_enrollment is not None:
        from app.services.transactional_notifications import (
            send_certificate_issued_notification,
            send_course_completed_notification,
        )

        await send_course_completed_notification(db, completed_enrollment)
        if certificate_id is not None:
            # Fetch certificate details for the notification
            from app.models.certificate import Certificate

            cert = await db.get(Certificate, certificate_id)
            if cert:
                await send_certificate_issued_notification(
                    db,
                    completed_enrollment,
                    certificate_number=cert.certificate_number,
                    validation_code=cert.validation_code,
                    certificate_id=cert.id,
                )

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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this course")

    student_id = await _get_student_id(db, current_user.get("user_id"))
    progress = await compute_course_progress(db, tenant_id, course_id, student_id)
    return CourseProgressDetailResponse(
        course_id=course_id,
        total_lessons=progress.total_lessons,
        required_lessons=progress.required_lessons,
        optional_lessons=progress.optional_lessons,
        completed_required=progress.completed_required,
        completed_optional=progress.completed_optional,
        percentage=progress.percentage,
        certificate_eligible=progress.certificate_eligible,
    )


# ─── Materials ───


@router.post("/{lesson_id}/materials/presign", response_model=MaterialUploadPresignResponse)
async def presign_material_upload(
    lesson_id: UUID,
    upload_data: MaterialUploadPresignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(Lesson).where(Lesson.id == lesson_id, Lesson.tenant_id == tenant_id)
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

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
    stmt = select(Lesson).where(Lesson.id == lesson_id, Lesson.tenant_id == tenant_id)
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

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
    stmt = select(Lesson).where(Lesson.id == lesson_id, Lesson.tenant_id == tenant_id)
    result = await db.execute(stmt)
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    if not lesson.is_free_preview:
        has_access = await _require_course_access(db, lesson.course_id, tenant_id, current_user)
        if not has_access:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this lesson")

    result = await db.execute(
        select(LessonMaterial).where(
            LessonMaterial.lesson_id == lesson_id,
            LessonMaterial.tenant_id == tenant_id,
        )
    )
    return result.scalars().all()


@router.get("/{lesson_id}/materials/{material_id}/download")
async def download_lesson_material(
    lesson_id: UUID,
    material_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    result = await db.execute(
        select(LessonMaterial).where(
            LessonMaterial.id == material_id,
            LessonMaterial.lesson_id == lesson_id,
            LessonMaterial.tenant_id == tenant_id,
        )
    )
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")

    lesson = (
        await db.execute(select(Lesson).where(Lesson.id == lesson_id, Lesson.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    if not lesson.is_free_preview:
        has_access = await _require_course_access(db, lesson.course_id, tenant_id, current_user)
        if not has_access:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this lesson")

    if material.storage_key:
        return {"download_url": await generate_material_download_url(material.storage_key)}
    if material.file_url:
        return {"download_url": material.file_url}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material file not available")


@router.delete("/{lesson_id}/materials/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lesson_material(
    lesson_id: UUID,
    material_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    result = await db.execute(
        select(LessonMaterial).where(
            LessonMaterial.id == material_id,
            LessonMaterial.lesson_id == lesson_id,
            LessonMaterial.tenant_id == tenant_id,
        )
    )
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")

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
    tenant_id = get_current_tenant_id()
    await _load_course_tenant_filtered(db, course_id, tenant_id)

    result = await db.execute(
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
    rows = result.all()

    required_count = await db.scalar(
        select(func.count(Lesson.id)).where(
            and_(Lesson.course_id == course_id, Lesson.tenant_id == tenant_id, Lesson.is_required == True)
        )
    ) or 0

    progress_list = []
    for enrollment, student, cls, user in rows:
        completed_required = await db.scalar(
            select(func.count(LessonProgress.id)).join(Lesson).where(
                and_(
                    LessonProgress.student_id == student.id,
                    LessonProgress.tenant_id == tenant_id,
                    Lesson.course_id == course_id,
                    LessonProgress.completed == True,
                    Lesson.is_required == True,
                )
            )
        ) or 0
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
) -> tuple[Enrollment | None, UUID | None]:
    """Issue the trusted certificate and conclude the correct enrollment once all required lessons are complete.

    The partial unique index allows historical revoked/superseded certificates while
    keeping at most one ACTIVE certificate for an enrollment. The insert is
    idempotent under concurrent/repeated completion requests.

    Returns (enrollment, certificate_id) if the enrollment was newly completed,
    (None, None) otherwise. The caller should send notifications AFTER committing.
    """
    total_lessons = (
        await db.execute(
            select(func.count(Lesson.id)).where(
                and_(
                    Lesson.course_id == course_id,
                    Lesson.tenant_id == tenant_id,
                    Lesson.is_required == True,
                )
            )
        )
    ).scalar() or 0
    completed_lessons = (
        await db.execute(
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
    ).scalar() or 0

    if total_lessons == 0 or completed_lessons < total_lessons:
        return None, None

    enrollment = (
        await db.execute(
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
                (Enrollment.status == EnrollmentStatus.CONFIRMADA).desc(),
                (Class.status == ClassStatus.EM_ANDAMENTO).desc(),
                (Class.status == ClassStatus.ABERTA).desc(),
                Class.start_date.desc(),
                Enrollment.enrollment_date.desc(),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if not enrollment:
        return None, None

    course = await _load_course_tenant_filtered(db, course_id, tenant_id)
    max_version = await db.scalar(
        select(func.coalesce(func.max(Certificate.version), 0)).where(
            Certificate.tenant_id == tenant_id,
            Certificate.enrollment_id == enrollment.id,
        )
    )
    version = int(max_version or 0) + 1
    issued_at = utc_now()
    expires_at = (
        issued_at + timedelta(days=course.certificate_validity_days)
        if course.certificate_validity_days
        else None
    )
    certificate_id = uuid4()
    certificate_number = generate_certificate_number()
    validation_code = generate_validation_code()
    content_hash = _content_hash(
        certificate_number=certificate_number,
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
        student_id=student_id,
        course_id=course_id,
        issued_at=issued_at,
        version=version,
    )

    cert_stmt = (
        insert(Certificate)
        .values(
            id=certificate_id,
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            certificate_number=certificate_number,
            validation_code=validation_code,
            issued_at=issued_at,
            expires_at=expires_at,
            status="ACTIVE",
            version=version,
            content_hash=content_hash,
        )
        .on_conflict_do_nothing(
            index_elements=["enrollment_id"],
            index_where=text("status = 'ACTIVE'"),
        )
        .returning(Certificate.id)
    )

    try:
        inserted_id = (await db.execute(cert_stmt)).scalar_one_or_none()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao emitir certificado",
        )

    if inserted_id:
        db.add(
            CertificateEvent(
                tenant_id=tenant_id,
                certificate_id=inserted_id,
                event_type="ISSUED",
                actor_id=None,
                details=f"version={version};hash={content_hash};source=course_completion",
            )
        )

    enrollment.status = EnrollmentStatus.CONCLUIDA
    return enrollment, inserted_id
