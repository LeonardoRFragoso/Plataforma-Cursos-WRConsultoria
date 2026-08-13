from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.core.security import get_current_user, get_current_admin
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.class_model import Class
from app.models.student import Student
from app.models.payment import Payment, PaymentStatus
from app.models.company import Company
from app.schemas.enrollment import (
    EnrollmentCreate,
    EnrollmentUpdate,
    EnrollmentResponse,
    BulkEnrollmentCreate,
    BulkEnrollmentResponse,
)

router = APIRouter()

@router.post("/", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def create_enrollment(
    enrollment_data: EnrollmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    stmt = select(Class).where(Class.id == enrollment_data.class_id)
    result = await db.execute(stmt)
    class_obj = result.scalar_one_or_none()
    
    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )
    
    enrollment = Enrollment(**enrollment_data.model_dump())
    db.add(enrollment)
    await db.commit()
    await db.refresh(enrollment)
    return enrollment

@router.get("/", response_model=List[EnrollmentResponse])
async def list_enrollments(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
    skip: int = 0,
    limit: int = 100,
):
    stmt = select(Enrollment).offset(skip).limit(limit)
    result = await db.execute(stmt)
    enrollments = result.scalars().all()
    return enrollments

@router.get("/{enrollment_id}", response_model=EnrollmentResponse)
async def get_enrollment(
    enrollment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    stmt = select(Enrollment).where(Enrollment.id == enrollment_id)
    result = await db.execute(stmt)
    enrollment = result.scalar_one_or_none()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found",
        )
    
    return enrollment

@router.put("/{enrollment_id}", response_model=EnrollmentResponse)
async def update_enrollment(
    enrollment_id: UUID,
    enrollment_data: EnrollmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    stmt = select(Enrollment).where(Enrollment.id == enrollment_id)
    result = await db.execute(stmt)
    enrollment = result.scalar_one_or_none()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found",
        )
    
    update_data = enrollment_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(enrollment, field, value)
    
    await db.commit()
    await db.refresh(enrollment)
    return enrollment

@router.delete("/{enrollment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_enrollment(
    enrollment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    stmt = select(Enrollment).where(Enrollment.id == enrollment_id)
    result = await db.execute(stmt)
    enrollment = result.scalar_one_or_none()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found",
        )
    
    await db.delete(enrollment)
    await db.commit()


@router.post("/bulk", response_model=BulkEnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def create_bulk_enrollments(
    data: BulkEnrollmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Cria múltiplas matrículas e um pagamento consolidado por empresa."""
    # Validar turma
    stmt = select(Class).where(Class.id == data.class_id)
    result = await db.execute(stmt)
    class_obj = result.scalar_one_or_none()
    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    # Validar empresa, se informada
    if data.company_id:
        stmt = select(Company).where(Company.id == data.company_id)
        result = await db.execute(stmt)
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found",
            )

    # Validar alunos
    stmt = select(Student).where(Student.id.in_(data.student_ids))
    result = await db.execute(stmt)
    students = result.scalars().all()
    found_ids = {str(s.id) for s in students}
    missing = [sid for sid in data.student_ids if str(sid) not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Students not found: {missing}",
        )

    # Criar matrículas
    enrollments = []
    for student_id in data.student_ids:
        enrollment = Enrollment(
            student_id=student_id,
            class_id=data.class_id,
            price=data.price_per_student,
            status=data.status,
        )
        db.add(enrollment)
        enrollments.append(enrollment)

    await db.flush()

    # Criar pagamento consolidado
    total_amount = data.price_per_student * len(data.student_ids)
    payment = Payment(
        enrollment_id=None,
        company_id=data.company_id,
        amount=total_amount,
        status=PaymentStatus.PENDENTE,
        method=data.payment_method,
        installments=data.installments,
    )
    db.add(payment)

    await db.commit()
    for enrollment in enrollments:
        await db.refresh(enrollment)
    await db.refresh(payment)

    return BulkEnrollmentResponse(
        enrollment_ids=[e.id for e in enrollments],
        payment_id=payment.id,
        total_amount=total_amount,
    )
