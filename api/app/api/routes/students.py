from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from uuid import UUID
import secrets

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_user, hash_password
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.student import StudentCreate, StudentUpdate, StudentResponse

router = APIRouter()


def _clean_cpf(cpf: str) -> str:
    """Remove formatação do CPF."""
    return cpf.replace('.', '').replace('-', '').strip()


@router.post("/", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    student_data: StudentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    raw_cpf = _clean_cpf(student_data.cpf)

    # Verificar CPF duplicado
    if raw_cpf:
        stmt = select(Student).where(Student.cpf == raw_cpf)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Student with this CPF already exists",
            )

        stmt = select(User).where(User.cpf == raw_cpf)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this CPF already exists",
            )

    # Verificar email duplicado
    stmt = select(User).where(User.email == str(student_data.email))
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Gerar senha temporária se não fornecida
    temp_password = student_data.password or secrets.token_urlsafe(8)

    # Criar User
    user = User(
        email=str(student_data.email),
        cpf=raw_cpf or None,
        full_name=student_data.full_name,
        password_hash=hash_password(temp_password),
        role=UserRole.STUDENT,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # Criar Student vinculado ao User
    student_payload = student_data.model_dump(exclude={"email", "full_name", "password"})
    student = Student(
        user_id=user.id,
        cpf=raw_cpf,
        **student_payload,
    )
    db.add(student)

    await db.commit()
    await db.refresh(student)
    await db.refresh(student, ["user"])
    student.temp_password = temp_password

    return student

@router.get("/", response_model=List[StudentResponse])
async def list_students(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
    skip: int = 0,
    limit: int = 100,
):
    stmt = select(Student).options(selectinload(Student.user)).offset(skip).limit(limit)
    result = await db.execute(stmt)
    students = result.scalars().all()
    return students

@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    stmt = select(Student).where(Student.id == student_id).options(selectinload(Student.user))
    result = await db.execute(stmt)
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )
    
    return student

@router.put("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: UUID,
    student_data: StudentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    stmt = select(Student).where(Student.id == student_id).options(selectinload(Student.user))
    result = await db.execute(stmt)
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )
    
    update_data = student_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(student, field, value)
    
    await db.commit()
    await db.refresh(student)
    await db.refresh(student, ["user"])
    return student

@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    stmt = select(Student).where(Student.id == student_id)
    result = await db.execute(stmt)
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )
    
    await db.delete(student)
    await db.commit()
