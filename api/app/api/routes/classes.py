from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.class_model import Class, ClassStatus
from app.models.course import Course, CourseModality
from app.models.user import User, UserRole
from app.schemas.class_schema import ClassCreate, ClassResponse, ClassUpdate

router = APIRouter()


def _generate_ead_access_link(course_id: UUID) -> str:
    """Generate the canonical platform EAD access URL for a course.

    Uses the configured FRONTEND_URL (the public web application base URL)
    + the authenticated learning route. This is the platform's own access
    point — NOT an external meeting link.
    """
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/courses/{course_id}/learn"


@router.post("/", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
async def create_class(
    class_data: ClassCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    course = await db.get(Course, class_data.course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )
    if not course.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course must be active to create a class",
        )

    responsible = await db.get(User, class_data.responsible_admin_id)
    if not responsible or not responsible.is_active or responsible.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Responsible user must be an active admin",
        )

    if class_data.start_date >= class_data.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date must be before end date",
        )

    if class_data.max_students <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="max_students must be greater than zero",
        )

    if class_data.status == ClassStatus.CANCELADA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create a class with CANCELADA status",
        )

    # Auto-generate EAD access link for EAD and SEMIPRESENCIAL courses
    # when the admin hasn't provided one. The platform's own learning route
    # is the canonical access point — admins should not need to manually
    # invent a URL.
    ead_link = class_data.ead_link
    if course.modality in (CourseModality.EAD, CourseModality.SEMIPRESENCIAL) and not ead_link:
        ead_link = _generate_ead_access_link(course.id)

    if course.modality == CourseModality.PRESENCIAL and not class_data.location:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="In-person classes require a location",
        )

    if course.modality == CourseModality.SEMIPRESENCIAL and not (class_data.location or ead_link):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hybrid classes require a location or ead_link",
        )

    # Build the class with the auto-generated ead_link if applicable
    class_dict = class_data.model_dump()
    class_dict["ead_link"] = ead_link
    class_obj = Class(**class_dict)
    db.add(class_obj)
    await db.commit()
    await db.refresh(class_obj)
    return class_obj

@router.get("/", response_model=list[ClassResponse])
async def list_classes(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
):
    stmt = select(Class).offset(skip).limit(limit)
    result = await db.execute(stmt)
    classes = result.scalars().all()
    return classes

@router.get("/{class_id}", response_model=ClassResponse)
async def get_class(class_id: UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(Class).where(Class.id == class_id)
    result = await db.execute(stmt)
    class_obj = result.scalar_one_or_none()
    
    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )
    
    return class_obj

@router.put("/{class_id}", response_model=ClassResponse)
async def update_class(
    class_id: UUID,
    class_data: ClassUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    stmt = select(Class).where(Class.id == class_id)
    result = await db.execute(stmt)
    class_obj = result.scalar_one_or_none()
    
    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )
    
    update_data = class_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(class_obj, field, value)
    
    await db.commit()
    await db.refresh(class_obj)
    return class_obj

@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_class(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    stmt = select(Class).where(Class.id == class_id)
    result = await db.execute(stmt)
    class_obj = result.scalar_one_or_none()
    
    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )
    
    await db.delete(class_obj)
    await db.commit()
