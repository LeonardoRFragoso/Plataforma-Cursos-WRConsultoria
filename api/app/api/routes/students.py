import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_user, hash_password
from app.models.attendance import Attendance
from app.models.certificate import Certificate
from app.models.class_model import Class, ClassStatus
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.lesson import LessonProgress
from app.models.payment import Payment
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.student import StudentCreate, StudentResponse, StudentUpdate

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

    # Validar turma e curso com lock de linha
    stmt = select(Class).where(Class.id == student_data.class_id).with_for_update()
    result = await db.execute(stmt)
    class_obj = result.scalar_one_or_none()
    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    if class_obj.status != ClassStatus.ABERTA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Class is not open for enrollment",
        )

    course = await db.get(Course, class_obj.course_id)
    if not course or not course.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course not found or inactive for the selected class",
        )

    # Verificar capacidade (apenas matrículas ativas)
    count_stmt = (
        select(func.count(Enrollment.id))
        .where(
            Enrollment.class_id == class_obj.id,
            Enrollment.status.in_([EnrollmentStatus.PENDENTE, EnrollmentStatus.CONFIRMADA]),
        )
    )
    count = (await db.execute(count_stmt)).scalar_one()
    if count >= class_obj.max_students:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Class is full",
        )

    # Gerar senha temporária se não fornecida
    temp_password = student_data.password or secrets.token_urlsafe(8)

    try:
        # Criar User, Student e Enrollment na mesma transação
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

        student_payload = student_data.model_dump(exclude={"email", "full_name", "password", "cpf", "class_id"})
        student = Student(
            user_id=user.id,
            cpf=raw_cpf,
            **student_payload,
        )
        db.add(student)
        await db.flush()

        # Verificar duplicidade de matrícula
        existing = (
            await db.execute(
                select(Enrollment).where(
                    Enrollment.student_id == student.id,
                    Enrollment.class_id == class_obj.id,
                )
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Student already enrolled in this class",
            )

        enrollment = Enrollment(
            student_id=student.id,
            class_id=class_obj.id,
            price=course.price,
            status=EnrollmentStatus.PENDENTE,
        )
        db.add(enrollment)

        await db.commit()
        await db.refresh(student)
        await db.refresh(student, ["user"])
        student.temp_password = temp_password

        return student

    except Exception:
        await db.rollback()
        raise

@router.get("/", response_model=list[StudentResponse])
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
    
    # Verificar histórico acadêmico/financeiro vinculado
    enrollments = (
        await db.execute(select(Enrollment).where(Enrollment.student_id == student_id))
    ).scalars().all()
    enrollment_ids = [enrollment.id for enrollment in enrollments]

    if enrollment_ids:
        has_payment = (
            await db.execute(
                select(func.count(Payment.id)).where(Payment.enrollment_id.in_(enrollment_ids))
            )
        ).scalar_one() > 0
        has_certificate = (
            await db.execute(
                select(func.count(Certificate.id)).where(Certificate.enrollment_id.in_(enrollment_ids))
            )
        ).scalar_one() > 0
        has_attendance = (
            await db.execute(
                select(func.count(Attendance.id)).where(Attendance.enrollment_id.in_(enrollment_ids))
            )
        ).scalar_one() > 0

        if has_payment or has_certificate or has_attendance:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete student with related payments, certificates or attendance records",
            )

    has_progress = (
        await db.execute(
            select(func.count(LessonProgress.id)).where(LessonProgress.student_id == student_id)
        )
    ).scalar_one() > 0
    if has_progress:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete student with lesson progress",
        )

    user = await db.get(User, student.user_id)

    for enrollment in enrollments:
        await db.delete(enrollment)

    await db.delete(student)
    if user:
        await db.delete(user)

    await db.commit()
