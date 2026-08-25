from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id, get_current_user
from app.models.class_model import Class, ClassStatus
from app.models.company import Company
from app.models.corporate_enrollment_batch import CorporateEnrollmentBatch
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentSource, EnrollmentStatus
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
from app.services.financial_lifecycle import expire_abandoned_internal_attempt

router = APIRouter()


@router.post("/", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def create_enrollment(
    enrollment_data: EnrollmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    stmt = select(Class).where(
        Class.id == enrollment_data.class_id,
        Class.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    class_obj = result.scalar_one_or_none()

    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    enrollment = Enrollment(tenant_id=tenant_id, **enrollment_data.model_dump())
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
    tenant_id = get_current_tenant_id()
    stmt = (
        select(Enrollment)
        .where(Enrollment.tenant_id == tenant_id)
        .offset(skip)
        .limit(limit)
    )
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

    tenant_id = get_current_tenant_id()
    user_id = UUID(current_user["user_id"])
    stmt = select(Student).where(
        Student.user_id == user_id,
        Student.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    student = result.scalar_one_or_none()
    if not student:
        return []

    stmt = (
        select(Enrollment, Class, Course)
        .join(Class, Enrollment.class_id == Class.id)
        .join(Course, Class.course_id == Course.id)
        .where(
            Enrollment.student_id == student.id,
            Enrollment.tenant_id == tenant_id,
        )
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        MyEnrollmentResponse(
            id=enrollment.id,
            status=enrollment.status,
            course_id=course.id,
            course_name=course.name,
            course_code=course.code,
            course_category=course.category,
            cover_image_url=course.cover_image_url,
            cover_image_alt=course.cover_image_alt,
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
    tenant_id = get_current_tenant_id()
    stmt = select(Enrollment).where(
        Enrollment.id == enrollment_id,
        Enrollment.tenant_id == tenant_id,
    )
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
    tenant_id = get_current_tenant_id()
    stmt = select(Enrollment).where(
        Enrollment.id == enrollment_id,
        Enrollment.tenant_id == tenant_id,
    )
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
    tenant_id = get_current_tenant_id()
    stmt = select(Enrollment).where(
        Enrollment.id == enrollment_id,
        Enrollment.tenant_id == tenant_id,
    )
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
    """Purchase a course with course-level and payment-attempt idempotency.

    Business rules (across every class of the same course):
    - CONFIRMADA / CONCLUIDA: the course is already acquired; return the
      existing enrollment and never create another charge.
    - PENDENTE + paid course: reuse only an active payment attempt
      (PENDENTE/PROCESSANDO). RECUSADO/REEMBOLSADO/EXPIRADO attempts remain
      immutable history and a new Payment row is created.
    - A provider-less PENDENTE attempt older than the configured TTL may be
      expired locally before creating the replacement attempt. Attempts with
      external provider evidence are never expired by the local timer.
    - PENDENTE enrollment + APROVADO payment: require manual reconciliation;
      never create another charge automatically (e.g. amount mismatch case).
    - Free course (price <= 0): confirm the enrollment directly and never
      create a Payment or contact a payment provider.
    - CANCELADA: a new enrollment may be created in another open class.

    Concurrency: the Student row serializes simultaneous purchases by the same
    user and the Class row is locked while capacity is checked. This protects
    against double-click/two-tab duplicate purchases at the database boundary.
    """
    if current_user.get("role") != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can purchase",
        )

    # Resolve tenant: prefer ContextVar (set by middleware), fall back to
    # current_user dict (set by JWT), then db.info (set by test harness).
    try:
        tenant_id = get_current_tenant_id()
    except HTTPException:
        tenant_id = None
        if current_user.get("tenant_id"):
            tenant_id = UUID(current_user["tenant_id"])
        elif db.info.get("tenant_id"):
            tenant_id = db.info["tenant_id"]
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant not resolved",
            )

    user_id = UUID(current_user["user_id"])

    # Lock the Student to serialize concurrent purchases from the same account.
    stmt = (
        select(Student)
        .where(
            Student.user_id == user_id,
            Student.tenant_id == tenant_id,
        )
        .with_for_update()
    )
    result = await db.execute(stmt)
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student profile not found",
        )

    stmt = select(Course).where(
        Course.id == data.course_id,
        Course.tenant_id == tenant_id,
    )
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

    is_free_course = float(course.price or 0) <= 0

    # Course-level idempotency: find any enrollment for this student/course.
    existing_stmt = (
        select(Enrollment)
        .join(Class, Enrollment.class_id == Class.id)
        .where(
            Enrollment.student_id == student.id,
            Enrollment.tenant_id == tenant_id,
            Class.course_id == course.id,
        )
    )
    existing_enrollments = (await db.execute(existing_stmt)).scalars().all()

    async def _payments_for(enrollment: Enrollment) -> list[Payment]:
        return (
            await db.execute(
                select(Payment)
                .where(
                    Payment.enrollment_id == enrollment.id,
                    Payment.tenant_id == tenant_id,
                )
                .order_by(Payment.created_at.desc(), Payment.id.desc())
            )
        ).scalars().all()

    async def _payment_for_acquired(enrollment: Enrollment) -> Payment | None:
        """Return evidence of a paid acquisition without creating a charge."""
        if float(enrollment.price or 0) <= 0:
            return None
        payments = await _payments_for(enrollment)
        approved = next((p for p in payments if p.status == PaymentStatus.APROVADO), None)
        return approved or (payments[0] if payments else None)

    async def _active_or_new_attempt(enrollment: Enrollment) -> Payment:
        """Reuse active attempts and preserve terminal financial history."""
        payments = await _payments_for(enrollment)
        latest = payments[0] if payments else None

        # A stale internal attempt that never reached a provider is safe to
        # expire. If a provider id/URL exists, the provider remains authoritative
        # and the attempt continues to be reused until a webhook closes it.
        if latest:
            expire_abandoned_internal_attempt(latest)

        if latest and latest.status in (
            PaymentStatus.PENDENTE,
            PaymentStatus.PROCESSANDO,
        ):
            return latest

        if latest and latest.status == PaymentStatus.APROVADO:
            # An approved payment with a still-pending enrollment indicates an
            # exceptional reconciliation state (for example, provider amount
            # mismatch). Starting a second charge could double-charge the user.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Payment approved but enrollment is pending; "
                    "manual reconciliation is required"
                ),
            )

        payment = Payment(
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            amount=enrollment.price,
            status=PaymentStatus.PENDENTE,
            method=data.method,
        )
        db.add(payment)
        await db.commit()
        await db.refresh(payment)
        return payment

    # Course already acquired: never create another payment/charge.
    acquired = [
        e
        for e in existing_enrollments
        if e.status in (EnrollmentStatus.CONFIRMADA, EnrollmentStatus.CONCLUIDA)
    ]
    if acquired:
        enrollment = acquired[0]
        payment = await _payment_for_acquired(enrollment)
        return EnrollmentPurchaseResponse(
            enrollment=enrollment,
            payment=PaymentResponse.model_validate(payment) if payment else None,
        )

    # Pending free enrollment (including legacy data): confirm directly.
    pending = [e for e in existing_enrollments if e.status == EnrollmentStatus.PENDENTE]
    if pending:
        enrollment = pending[0]
        if is_free_course:
            enrollment.price = 0
            enrollment.status = EnrollmentStatus.CONFIRMADA
            await db.commit()
            await db.refresh(enrollment)
            return EnrollmentPurchaseResponse(enrollment=enrollment, payment=None)

        payment = await _active_or_new_attempt(enrollment)
        return EnrollmentPurchaseResponse(
            enrollment=enrollment,
            payment=PaymentResponse.model_validate(payment),
        )

    # No reusable enrollment (only CANCELADA or none): choose an open class.
    stmt = (
        select(Class)
        .where(
            Class.course_id == course.id,
            Class.tenant_id == tenant_id,
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
        # Lock class while checking capacity.
        locked = (
            await db.execute(
                select(Class)
                .where(
                    Class.id == class_obj.id,
                    Class.tenant_id == tenant_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if not locked:
            continue

        # A unique (tenant, student, class) constraint prevents a second row in
        # the same class. A CANCELADA row therefore cannot be silently reused.
        already_in_class = any(e.class_id == class_obj.id for e in existing_enrollments)
        if already_in_class:
            continue

        count_stmt = select(func.count(Enrollment.id)).where(
            Enrollment.class_id == class_obj.id,
            Enrollment.tenant_id == tenant_id,
            Enrollment.status != EnrollmentStatus.CANCELADA,
        )
        enrolled = (await db.execute(count_stmt)).scalar_one()
        if enrolled >= class_obj.max_students:
            continue

        enrollment = Enrollment(
            tenant_id=tenant_id,
            student_id=student.id,
            class_id=class_obj.id,
            price=0 if is_free_course else course.price,
            status=(
                EnrollmentStatus.CONFIRMADA
                if is_free_course
                else EnrollmentStatus.PENDENTE
            ),
            source=EnrollmentSource.INDIVIDUAL,
        )
        db.add(enrollment)
        await db.flush()

        # Free courses never create a financial record or contact a provider.
        if is_free_course:
            await db.commit()
            await db.refresh(enrollment)
            return EnrollmentPurchaseResponse(enrollment=enrollment, payment=None)

        payment = Payment(
            tenant_id=tenant_id,
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
    """Bulk enrollment for corporate provisioning.

    Creates multiple enrollments atomically. When create_payment=False
    (default for corporate), no Payment is created — access is provisioned
    under an external corporate contract.

    When create_payment=True, a consolidated payment is created.

    Capacity is checked BEFORE any writes. If there are not enough seats,
    NO enrollments are created (atomic behavior).
    """
    tenant_id = get_current_tenant_id()

    # Validate class (tenant-scoped, with lock)
    stmt = (
        select(Class)
        .where(Class.id == data.class_id, Class.tenant_id == tenant_id)
        .with_for_update()
    )
    result = await db.execute(stmt)
    class_obj = result.scalar_one_or_none()
    if not class_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    # Validate company (tenant-scoped)
    if data.company_id:
        stmt = select(Company).where(
            Company.id == data.company_id,
            Company.tenant_id == tenant_id,
        )
        result = await db.execute(stmt)
        company = result.scalar_one_or_none()
        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    # Validate students (tenant-scoped)
    stmt = (
        select(Student)
        .where(
            Student.id.in_(data.student_ids),
            Student.tenant_id == tenant_id,
        )
        .options(selectinload(Student.user))
    )
    result = await db.execute(stmt)
    students = result.scalars().all()
    found_ids = {s.id for s in students}
    missing = [sid for sid in data.student_ids if sid not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Students not found: {missing}",
        )

    # If company_id provided, verify all students belong to that company
    if data.company_id:
        wrong_company = [s for s in students if s.company_id != data.company_id]
        if wrong_company:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Some students do not belong to the specified company",
            )

    # Check for duplicate enrollments
    stmt = select(Enrollment).where(
        Enrollment.student_id.in_(data.student_ids),
        Enrollment.class_id == data.class_id,
        Enrollment.tenant_id == tenant_id,
        Enrollment.status != EnrollmentStatus.CANCELADA,
    )
    existing = (await db.execute(stmt)).scalars().all()
    if existing:
        already_enrolled = [str(e.student_id) for e in existing]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Some students are already enrolled in this class: {already_enrolled}",
        )

    # Check capacity BEFORE any writes (atomic)
    count_stmt = select(func.count(Enrollment.id)).where(
        Enrollment.class_id == data.class_id,
        Enrollment.tenant_id == tenant_id,
        Enrollment.status.in_([EnrollmentStatus.PENDENTE, EnrollmentStatus.CONFIRMADA]),
    )
    current_count = (await db.execute(count_stmt)).scalar_one()
    available = class_obj.max_students - current_count
    requested = len(data.student_ids)
    if requested > available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient capacity: {requested} requested, {available} available",
        )

    # Create enrollments
    enrollments = []
    for student in students:
        enrollment = Enrollment(
            tenant_id=tenant_id,
            student_id=student.id,
            class_id=data.class_id,
            price=data.price_per_student,
            status=data.status,
            source=data.source,
        )
        db.add(enrollment)
        enrollments.append(enrollment)

    await db.flush()

    # Optional payment
    payment = None
    total_amount = data.price_per_student * len(data.student_ids)
    if data.create_payment and data.payment_method:
        payment = Payment(
            tenant_id=tenant_id,
            enrollment_id=None,
            company_id=data.company_id,
            amount=total_amount,
            status=PaymentStatus.PENDENTE,
            method=data.payment_method,
            installments=data.installments,
        )
        db.add(payment)
        await db.flush()

    # Create audit batch record (only for corporate enrollments with company_id)
    batch = None
    if data.company_id:
        batch = CorporateEnrollmentBatch(
            tenant_id=tenant_id,
            company_id=data.company_id,
            class_id=data.class_id,
            enrollment_count=len(data.student_ids),
            created_by=UUID(current_user["user_id"]) if current_user.get("user_id") else None,
            created_by_name=current_user.get("full_name"),
        )
        db.add(batch)

    await db.commit()
    for enrollment in enrollments:
        await db.refresh(enrollment)
    if payment:
        await db.refresh(payment)
    if batch:
        await db.refresh(batch)

    return BulkEnrollmentResponse(
        enrollment_ids=[e.id for e in enrollments],
        payment_id=payment.id if payment else None,
        total_amount=total_amount,
        batch_id=batch.id if batch else None,
    )
