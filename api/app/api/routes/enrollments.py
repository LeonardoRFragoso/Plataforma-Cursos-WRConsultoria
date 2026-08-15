from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_user
from app.models.class_model import Class, ClassStatus
from app.models.company import Company
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.payment import Payment, PaymentStatus
from app.models.student import Student
from app.schemas.enrollment import (
    BulkEnrollmentCreate,
    BulkEnrollmentResponse,
    EnrollmentCreate,
    EnrollmentPurchaseRequest,
    EnrollmentPurchaseResponse,
    EnrollmentResponse,
    EnrollmentUpdate,
    MyEnrollmentResponse,
)
from app.schemas.payment import PaymentResponse

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

@router.get("/", response_model=list[EnrollmentResponse])
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

@router.get("/me", response_model=list[MyEnrollmentResponse])
async def list_my_enrollments(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "student":
        return []

    user_id = UUID(current_user["user_id"])
    stmt = select(Student).where(Student.user_id == user_id)
    result = await db.execute(stmt)
    student = result.scalar_one_or_none()
    if not student:
        return []

    stmt = (
        select(Enrollment, Class, Course)
        .join(Class, Enrollment.class_id == Class.id)
        .join(Course, Class.course_id == Course.id)
        .where(Enrollment.student_id == student.id)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        MyEnrollmentResponse(
            id=enrollment.id,
            status=enrollment.status,
            course_id=course.id,
            course_name=course.name,
            class_id=class_obj.id,
            start_date=class_obj.start_date,
            end_date=class_obj.end_date,
            enrollment_date=enrollment.enrollment_date,
        )
        for enrollment, class_obj, course in rows
    ]


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


@router.post("/purchase", response_model=EnrollmentPurchaseResponse, status_code=status.HTTP_201_CREATED)
async def purchase_enrollment(
    data: EnrollmentPurchaseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can purchase",
        )

    user_id = UUID(current_user["user_id"])
    stmt = select(Student).where(Student.user_id == user_id)
    result = await db.execute(stmt)
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student profile not found",
        )

    stmt = select(Course).where(Course.id == data.course_id)
    result = await db.execute(stmt)
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )
    if not course.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course not available",
        )

    stmt = (
        select(Class)
        .where(
            Class.course_id == course.id,
            Class.status == ClassStatus.ABERTA,
        )
        .order_by(Class.start_date.asc())
    )
    result = await db.execute(stmt)
    open_classes = result.scalars().all()
    if not open_classes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No open class for this course",
        )

    for class_obj in open_classes:
        count_stmt = (
            select(func.count(Enrollment.id))
            .where(
                Enrollment.class_id == class_obj.id,
                Enrollment.status != EnrollmentStatus.CANCELADA,
            )
        )
        enrolled = (await db.execute(count_stmt)).scalar_one()
        if enrolled >= class_obj.max_students:
            continue

        stmt = select(Enrollment).where(
            Enrollment.student_id == student.id,
            Enrollment.class_id == class_obj.id,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            if existing.status == EnrollmentStatus.CANCELADA:
                continue
            payment = (
                await db.execute(select(Payment).where(Payment.enrollment_id == existing.id))
            ).scalar_one_or_none()
            if not payment:
                payment = Payment(
                    enrollment_id=existing.id,
                    amount=existing.price,
                    status=PaymentStatus.PENDENTE,
                    method=data.method,
                )
                db.add(payment)
                await db.commit()
                await db.refresh(payment)
            return EnrollmentPurchaseResponse(
                enrollment=existing,
                payment=PaymentResponse.model_validate(payment),
            )

        enrollment = Enrollment(
            student_id=student.id,
            class_id=class_obj.id,
            price=course.price,
            status=EnrollmentStatus.PENDENTE,
        )
        db.add(enrollment)
        await db.flush()

        payment = Payment(
            enrollment_id=enrollment.id,
            amount=course.price,
            status=PaymentStatus.PENDENTE,
            method=data.method,
        )
        db.add(payment)
        await db.commit()
        await db.refresh(enrollment)
        await db.refresh(payment)

        return EnrollmentPurchaseResponse(
            enrollment=enrollment,
            payment=PaymentResponse.model_validate(payment),
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="No class with available seats",
    )


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
