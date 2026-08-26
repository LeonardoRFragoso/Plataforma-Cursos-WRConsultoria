"""API routes for CourseContentProfile — structured course content.

Public read access for enrolled/authenticated users.
Admin write access for managing content profiles.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id
from app.models.course import Course
from app.models.course_content_profile import CourseContentProfile
from app.schemas.course_content_profile import (
    CourseContentProfileCreate,
    CourseContentProfileResponse,
    CourseContentProfileUpdate,
)

router = APIRouter()


@router.get("/courses/{course_id}/content-profile", response_model=CourseContentProfileResponse)
async def get_content_profile(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Public read: get the structured content profile for a course."""
    tenant_id = get_current_tenant_id()
    result = await db.execute(
        select(CourseContentProfile).where(
            CourseContentProfile.course_id == course_id,
            CourseContentProfile.tenant_id == tenant_id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content profile not found",
        )
    return profile


@router.post("/courses/{course_id}/content-profile", response_model=CourseContentProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_content_profile(
    course_id: UUID,
    profile_data: CourseContentProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Admin only: create a content profile for a course."""
    tenant_id = get_current_tenant_id()

    # Verify course exists and belongs to tenant
    course = (
        await db.execute(select(Course).where(Course.id == course_id, Course.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    # Check if profile already exists
    existing = (
        await db.execute(
            select(CourseContentProfile).where(
                CourseContentProfile.course_id == course_id,
                CourseContentProfile.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Content profile already exists for this course",
        )

    data = profile_data.model_dump(exclude={"course_id"})
    profile = CourseContentProfile(
        tenant_id=tenant_id,
        course_id=course_id,
        **data,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.put("/courses/{course_id}/content-profile", response_model=CourseContentProfileResponse)
async def update_content_profile(
    course_id: UUID,
    profile_data: CourseContentProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Admin only: update a content profile."""
    tenant_id = get_current_tenant_id()
    result = await db.execute(
        select(CourseContentProfile).where(
            CourseContentProfile.course_id == course_id,
            CourseContentProfile.tenant_id == tenant_id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content profile not found",
        )

    update_data = profile_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)

    await db.commit()
    await db.refresh(profile)
    return profile
