import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.normalization import normalize_cpf, normalize_email, validate_cpf
from app.core.security import get_current_admin, get_current_tenant_id, get_current_user, hash_password
from app.models.attendance import Attendance
from app.models.certificate import Certificate
from app.models.class_model import Class, ClassStatus
from app.models.company import Company
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.lesson import LessonProgress
from app.models.payment import Payment
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.student import StudentCreate, StudentResponse, StudentUpdate
from app.services.email_service import EmailServiceError, get_email_service
from app.services.one_time_token_service import OneTimeTokenService

router = APIRouter()

# Environments where raw one-time tokens may be returned in responses.
# Only local development and automated test environments.
_LOCAL_TOKEN_RETURN_ENVS = frozenset({"development", "dev", "test", "testing"})


def _current_env() -> str:
    return getattr(settings, "ENVIRONMENT", "").lower()


def _can_return_token() -> bool:
    """Only local dev/test environments may return raw one-time tokens."""
    return _current_env() in _LOCAL_TOKEN_RETURN_ENVS


def _clean_cpf(cpf: str) -> str:
    """Remove formatação do CPF usando o helper centralizado de normalização."""
    if not cpf:
        return ""
    return normalize_cpf(cpf)


@router.post("/", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    student_data: StudentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Create a student.

    When class_id is provided, an enrollment is created (legacy behavior).
    When class_id is omitted, only the User + Student are created —
    enrollment can be done separately later.

    When company_id is provided, the student is linked to that company
    (corporate student). When omitted, the student is independent (B2C).

    When no password is provided, the user is created without a password
    and an activation token is generated so the student can set their own.
    """
    tenant_id = get_current_tenant_id()

    # Strict CPF validation when CPF is provided
    raw_cpf = ""
    if student_data.cpf:
        try:
            raw_cpf = validate_cpf(student_data.cpf)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CPF inválido",
            )

    # Validate company_id belongs to tenant if provided
    if student_data.company_id:
        stmt = select(Company).where(
            Company.id == student_data.company_id,
            Company.tenant_id == tenant_id,
        )
        result = await db.execute(stmt)
        company = result.scalar_one_or_none()
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found",
            )

    # Check duplicate CPF (tenant-scoped)
    if raw_cpf:
        stmt = select(User).where(
            User.tenant_id == tenant_id,
            User.cpf == raw_cpf,
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this CPF already exists",
            )

    # Check duplicate email (tenant-scoped)
    normalized_student_email = normalize_email(str(student_data.email))
    stmt = select(User).where(
        User.tenant_id == tenant_id,
        User.email == normalized_student_email,
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Optional enrollment: validate class and course
    class_obj = None
    course = None
    if student_data.class_id:
        stmt = select(Class).where(
            Class.id == student_data.class_id,
            Class.tenant_id == tenant_id,
        ).with_for_update()
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

        # Check capacity
        count_stmt = (
            select(func.count(Enrollment.id))
            .where(
                Enrollment.class_id == class_obj.id,
                Enrollment.tenant_id == tenant_id,
                Enrollment.status.in_([EnrollmentStatus.PENDENTE, EnrollmentStatus.CONFIRMADA]),
            )
        )
        count = (await db.execute(count_stmt)).scalar_one()
        if count >= class_obj.max_students:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Class is full",
            )

    # Determine password handling
    has_password = bool(student_data.password)
    temp_password = student_data.password or (secrets.token_urlsafe(8) if student_data.class_id else None)

    try:
        user = User(
            tenant_id=tenant_id,
            email=normalized_student_email,
            cpf=raw_cpf or None,
            full_name=student_data.full_name,
            password_hash=hash_password(temp_password) if temp_password else None,
            role=UserRole.STUDENT,
            is_active=bool(temp_password),
        )
        db.add(user)
        await db.flush()

        student_payload = student_data.model_dump(
            exclude={"email", "full_name", "password", "cpf", "class_id"}
        )
        student = Student(
            tenant_id=tenant_id,
            user_id=user.id,
            cpf=raw_cpf,
            **student_payload,
        )
        # Set company name from relational company_id if not explicitly provided
        if student_data.company_id and not student.company:
            company_obj = await db.get(Company, student_data.company_id)
            if company_obj:
                student.company = company_obj.trade_name or company_obj.legal_name
        db.add(student)
        await db.flush()

        # Optional enrollment
        if class_obj and course:
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
                tenant_id=tenant_id,
                student_id=student.id,
                class_id=class_obj.id,
                price=course.price,
                status=EnrollmentStatus.PENDENTE,
            )
            db.add(enrollment)

        # Generate activation token if no password was set
        activation_token_value = None
        if not has_password and not temp_password:
            raw_token, _ = await OneTimeTokenService.create(
                db, str(user.id), "activation", ttl_hours=168,
            )
            # Only expose raw token in dev/test environments.
            # In production/staging, the token is sent via email and
            # NEVER appears in the HTTP response.
            if _can_return_token():
                activation_token_value = raw_token
            else:
                try:
                    email_service = get_email_service()
                    await email_service.send_account_activation(
                        to=user.email,
                        activation_token=raw_token,
                        frontend_url=settings.FRONTEND_URL,
                        tenant_name="Plataforma",
                    )
                except EmailServiceError:
                    pass
            student.activation_token = activation_token_value

        await db.commit()
        await db.refresh(student)
        await db.refresh(student, ["user"])
        if temp_password:
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
    company_id: UUID | None = None,
):
    tenant_id = get_current_tenant_id()
    stmt = (
        select(Student)
        .where(Student.tenant_id == tenant_id)
        .options(selectinload(Student.user))
    )
    if company_id:
        stmt = stmt.where(Student.company_id == company_id)
    stmt = stmt.offset(skip).limit(limit).order_by(Student.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    stmt = (
        select(Student)
        .where(
            Student.id == student_id,
            Student.tenant_id == tenant_id,
        )
        .options(selectinload(Student.user))
    )
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
    tenant_id = get_current_tenant_id()
    stmt = (
        select(Student)
        .where(
            Student.id == student_id,
            Student.tenant_id == tenant_id,
        )
        .options(selectinload(Student.user))
    )
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
    tenant_id = get_current_tenant_id()
    stmt = select(Student).where(
        Student.id == student_id,
        Student.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    # Check for related records
    enrollments = (
        await db.execute(
            select(Enrollment).where(
                Enrollment.student_id == student_id,
                Enrollment.tenant_id == tenant_id,
            )
        )
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
