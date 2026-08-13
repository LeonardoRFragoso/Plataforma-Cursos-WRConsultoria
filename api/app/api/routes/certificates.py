import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_user
from app.models.certificate import Certificate
from app.models.class_model import Class
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.student import Student
from app.models.user import User
from app.schemas.certificate import (
    CertificateCreate,
    CertificateResponse,
    CertificateValidationRequest,
    CertificateValidationResponse,
)

router = APIRouter()

def generate_certificate_number() -> str:
    return f"CERT-{uuid.uuid4().hex[:12].upper()}"

def generate_validation_code() -> str:
    return f"{uuid.uuid4().hex[:16].upper()}"

@router.post("/", response_model=CertificateResponse, status_code=status.HTTP_201_CREATED)
async def create_certificate(
    cert_data: CertificateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    stmt = select(Enrollment).where(Enrollment.id == cert_data.enrollment_id)
    result = await db.execute(stmt)
    enrollment = result.scalar_one_or_none()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found",
        )
    
    stmt = select(Certificate).where(Certificate.enrollment_id == cert_data.enrollment_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Certificate already exists for this enrollment",
        )
    
    certificate = Certificate(
        enrollment_id=cert_data.enrollment_id,
        certificate_number=generate_certificate_number(),
        validation_code=generate_validation_code(),
    )
    db.add(certificate)
    await db.commit()
    await db.refresh(certificate)
    return certificate

@router.get("/", response_model=list[CertificateResponse])
async def list_certificates(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
    skip: int = 0,
    limit: int = 100,
):
    stmt = select(Certificate).offset(skip).limit(limit)
    result = await db.execute(stmt)
    certificates = result.scalars().all()
    return certificates

@router.get("/{certificate_id}", response_model=CertificateResponse)
async def get_certificate(
    certificate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    stmt = select(Certificate).where(Certificate.id == certificate_id)
    result = await db.execute(stmt)
    certificate = result.scalar_one_or_none()
    
    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found",
        )
    
    return certificate

@router.post("/validate", response_model=CertificateValidationResponse)
async def validate_certificate(
    request: CertificateValidationRequest,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Certificate).where(Certificate.validation_code == request.validation_code)
    result = await db.execute(stmt)
    certificate = result.scalar_one_or_none()
    
    if not certificate:
        return CertificateValidationResponse(valid=False)
    
    stmt = select(Enrollment).where(Enrollment.id == certificate.enrollment_id)
    result = await db.execute(stmt)
    enrollment = result.scalar_one_or_none()
    
    stmt = select(Student).where(Student.id == enrollment.student_id)
    result = await db.execute(stmt)
    student = result.scalar_one_or_none()
    
    stmt = select(User).where(User.id == student.user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    stmt = select(Class).where(Class.id == enrollment.class_id)
    result = await db.execute(stmt)
    class_obj = result.scalar_one_or_none()
    
    stmt = select(Course).where(Course.id == class_obj.course_id)
    result = await db.execute(stmt)
    course = result.scalar_one_or_none()
    
    return CertificateValidationResponse(
        valid=True,
        certificate_number=certificate.certificate_number,
        student_name=user.full_name,
        course_name=course.name,
        issued_at=certificate.issued_at,
    )

@router.delete("/{certificate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_certificate(
    certificate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    stmt = select(Certificate).where(Certificate.id == certificate_id)
    result = await db.execute(stmt)
    certificate = result.scalar_one_or_none()
    
    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found",
        )
    
    await db.delete(certificate)
    await db.commit()
