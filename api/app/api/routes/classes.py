from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.class_model import Class
from app.models.course import Course
from app.schemas.class_schema import ClassCreate, ClassResponse, ClassUpdate

router = APIRouter()

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

    class_obj = Class(**class_data.model_dump())
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
