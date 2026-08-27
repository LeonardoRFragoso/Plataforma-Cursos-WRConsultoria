"""API routes for CourseMaterial — course-level downloadable materials.

Public list (for enrolled students), protected download, admin management.
Materials do NOT affect lesson progress or certificate issuance.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id, get_current_user
from app.core.storage import (
    generate_course_material_upload_url,
    generate_material_download_url,
    head_object_metadata,
    validate_storage_key_tenant_course,
)
from app.models.class_model import Class
from app.models.course import Course
from app.models.course_material import CourseMaterial
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.student import Student
from app.schemas.course_material import (
    CourseMaterialCompleteRequest,
    CourseMaterialCreate,
    CourseMaterialResponse,
    CourseMaterialUpdate,
    CourseMaterialUploadUrlRequest,
    CourseMaterialUploadUrlResponse,
)

router = APIRouter()


async def _check_course_access(db: AsyncSession, course_id: UUID, tenant_id: UUID, user: dict) -> bool:
    """Check if user has access to course materials (enrolled or admin)."""
    role = user.get("role", "").lower()
    if role in ("admin", "super_admin"):
        return True

    # Look up student from user_id
    user_id = user.get("user_id")
    if not user_id:
        return False

    student = (
        await db.execute(
            select(Student).where(Student.user_id == user_id, Student.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not student:
        return False

    # Check enrollment via class -> course relationship
    result = await db.execute(
        select(Enrollment)
        .join(Class, Enrollment.class_id == Class.id)
        .where(
            Class.course_id == course_id,
            Enrollment.tenant_id == tenant_id,
            Enrollment.student_id == student.id,
            Enrollment.status.in_([EnrollmentStatus.CONFIRMADA, EnrollmentStatus.CONCLUIDA]),
        )
    )
    return result.scalar_one_or_none() is not None


@router.get("/courses/{course_id}/materials", response_model=list[CourseMaterialResponse])
async def list_course_materials(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List active materials for a course. Requires enrollment or admin."""
    tenant_id = get_current_tenant_id()

    # Verify course exists
    course = (
        await db.execute(select(Course).where(Course.id == course_id, Course.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    # Check access
    has_access = await _check_course_access(db, course_id, tenant_id, current_user)
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this course materials",
        )

    result = await db.execute(
        select(CourseMaterial).where(
            CourseMaterial.course_id == course_id,
            CourseMaterial.tenant_id == tenant_id,
            CourseMaterial.is_active == True,
        ).order_by(CourseMaterial.created_at)
    )
    return result.scalars().all()


@router.post("/courses/{course_id}/materials", response_model=CourseMaterialResponse, status_code=status.HTTP_201_CREATED)
async def create_course_material(
    course_id: UUID,
    material_data: CourseMaterialCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Admin only: create a course material record."""
    tenant_id = get_current_tenant_id()

    course = (
        await db.execute(select(Course).where(Course.id == course_id, Course.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    # Check for duplicate (same sha256)
    if material_data.sha256:
        existing = (
            await db.execute(
                select(CourseMaterial).where(
                    CourseMaterial.course_id == course_id,
                    CourseMaterial.tenant_id == tenant_id,
                    CourseMaterial.sha256 == material_data.sha256,
                )
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Material with this SHA-256 already exists for this course",
            )

    material = CourseMaterial(
        tenant_id=tenant_id,
        course_id=course_id,
        title=material_data.title,
        storage_key=material_data.storage_key,
        mime_type=material_data.mime_type,
        size_bytes=material_data.size_bytes,
        sha256=material_data.sha256,
        document_type=material_data.document_type,
        is_active=material_data.is_active,
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)
    return material


@router.put("/courses/{course_id}/materials/{material_id}", response_model=CourseMaterialResponse)
async def update_course_material(
    course_id: UUID,
    material_id: UUID,
    material_data: CourseMaterialUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Admin only: update a course material."""
    tenant_id = get_current_tenant_id()
    result = await db.execute(
        select(CourseMaterial).where(
            CourseMaterial.id == material_id,
            CourseMaterial.course_id == course_id,
            CourseMaterial.tenant_id == tenant_id,
        )
    )
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")

    update_data = material_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(material, key, value)

    await db.commit()
    await db.refresh(material)
    return material


@router.delete("/courses/{course_id}/materials/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course_material(
    course_id: UUID,
    material_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Admin only: delete a course material (deactivate, not hard delete)."""
    tenant_id = get_current_tenant_id()
    result = await db.execute(
        select(CourseMaterial).where(
            CourseMaterial.id == material_id,
            CourseMaterial.course_id == course_id,
            CourseMaterial.tenant_id == tenant_id,
        )
    )
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")

    material.is_active = False
    await db.commit()


@router.get("/courses/{course_id}/materials/{material_id}/download")
async def download_course_material(
    course_id: UUID,
    material_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Download a course material. Requires enrollment or admin."""
    tenant_id = get_current_tenant_id()

    result = await db.execute(
        select(CourseMaterial).where(
            CourseMaterial.id == material_id,
            CourseMaterial.course_id == course_id,
            CourseMaterial.tenant_id == tenant_id,
            CourseMaterial.is_active == True,
        )
    )
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")

    # Check access
    has_access = await _check_course_access(db, course_id, tenant_id, current_user)
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this material",
        )

    download_url = await generate_material_download_url(material.storage_key)
    return {"download_url": download_url}


# ─── Presigned upload flow ───

@router.post(
    "/courses/{course_id}/materials/upload-url",
    response_model=CourseMaterialUploadUrlResponse,
)
async def create_course_material_upload_url(
    course_id: UUID,
    request: CourseMaterialUploadUrlRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Admin only: generate a presigned PUT URL for direct-to-storage upload.

    The client:
    1. Computes SHA-256 of the file locally
    2. Calls this endpoint with filename, mime_type, size_bytes, sha256
    3. Receives a presigned PUT URL and storage_key
    4. PUTs the file directly to storage (S3 or local backend)
    5. Calls POST /courses/{course_id}/materials/complete to finalize
    """
    tenant_id = get_current_tenant_id()

    course = (
        await db.execute(select(Course).where(Course.id == course_id, Course.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    # Check for duplicate SHA (already uploaded)
    existing = (
        await db.execute(
            select(CourseMaterial).where(
                CourseMaterial.course_id == course_id,
                CourseMaterial.tenant_id == tenant_id,
                CourseMaterial.sha256 == request.sha256,
                CourseMaterial.is_active == True,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Material with this SHA-256 already exists for this course",
        )

    upload_url, storage_key = await generate_course_material_upload_url(
        tenant_id=tenant_id,
        course_id=course_id,
        filename=request.filename,
        mime_type=request.mime_type,
        size_bytes=request.size_bytes,
        sha256=request.sha256,
    )

    return CourseMaterialUploadUrlResponse(
        upload_url=upload_url,
        storage_key=storage_key,
        expires_in=3600,
    )


@router.post(
    "/courses/{course_id}/materials/complete",
    response_model=CourseMaterialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def complete_course_material_upload(
    course_id: UUID,
    request: CourseMaterialCompleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Admin only: finalize a course material upload.

    Called after the client has successfully PUT the file to the
    presigned URL. The backend:
    1. Validates the storage_key belongs to this tenant+course
    2. Verifies the object actually exists in storage (head_object)
    3. Checks metadata (content length, content type) if available
    4. Checks for duplicate SHA-256
    5. Creates the CourseMaterial record
    """
    tenant_id = get_current_tenant_id()

    course = (
        await db.execute(select(Course).where(Course.id == course_id, Course.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    # Validate storage_key belongs to this tenant and course
    if not validate_storage_key_tenant_course(request.storage_key, tenant_id, course_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Storage key does not belong to this tenant/course",
        )

    # Verify object exists in storage
    metadata = await head_object_metadata(request.storage_key)
    if metadata is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Object not found in storage — upload may have failed",
        )

    # Validate metadata if available
    if metadata.get("content_length") is not None:
        actual_size = metadata["content_length"]
        if actual_size != request.size_bytes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Size mismatch: expected {request.size_bytes}, got {actual_size}",
            )

    # Check for duplicate SHA
    existing = (
        await db.execute(
            select(CourseMaterial).where(
                CourseMaterial.course_id == course_id,
                CourseMaterial.tenant_id == tenant_id,
                CourseMaterial.sha256 == request.sha256,
                CourseMaterial.is_active == True,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Material with this SHA-256 already exists for this course",
        )

    material = CourseMaterial(
        tenant_id=tenant_id,
        course_id=course_id,
        title=request.title,
        storage_key=request.storage_key,
        mime_type=request.mime_type,
        size_bytes=request.size_bytes,
        sha256=request.sha256,
        document_type=request.document_type,
        is_active=True,
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)
    return material
