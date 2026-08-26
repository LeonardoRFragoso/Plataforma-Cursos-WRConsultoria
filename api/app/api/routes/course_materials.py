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
from app.core.storage import generate_material_download_url
from app.models.class_model import Class
from app.models.course import Course
from app.models.course_material import CourseMaterial
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.student import Student
from app.schemas.course_material import (
    CourseMaterialCreate,
    CourseMaterialResponse,
    CourseMaterialUpdate,
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
