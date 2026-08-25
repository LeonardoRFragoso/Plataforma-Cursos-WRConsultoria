from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.normalization import normalize_email, validate_cpf
from app.core.security import get_current_admin, get_current_tenant_id
from app.core.utils import utc_now
from app.models.certificate import Certificate
from app.models.class_model import Class, ClassStatus
from app.models.company import Company
from app.models.corporate import CorporateInvite, CorporateSeatAllocation, CorporateTrainingRequest
from app.models.corporate_enrollment_batch import CorporateEnrollmentBatch
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentSource, EnrollmentStatus
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.corporate import (
    CorporateBulkEnrollRequest,
    CorporateBulkEnrollResponse,
    CorporateEmployeeReportRow,
    CorporateInviteCreate,
    CorporateInviteResponse,
    CorporateLinkEmployeeRequest,
    CorporateOffboardRequest,
    CorporateRequestCreate,
    CorporateRequestResponse,
    CorporateRequestUpdate,
    CorporateSeatAllocationCreate,
    CorporateSeatAllocationResponse,
    CorporateTrainingReport,
)
from app.services.email_service import EmailServiceError, get_email_service
from app.services.one_time_token_service import OneTimeTokenService

router = APIRouter()

_REQUEST_STATUSES = {"NEW", "CONTACTED", "QUALIFIED", "PROPOSAL_SENT", "WON", "LOST"}
_LOCAL_TOKEN_RETURN_ENVS = {"development", "dev", "test", "testing"}


def _clean_cnpj(value: str | None) -> str | None:
    if not value:
        return None
    return "".join(ch for ch in value if ch.isdigit()) or None


def _can_return_token() -> bool:
    return str(getattr(settings, "ENVIRONMENT", "")).lower() in _LOCAL_TOKEN_RETURN_ENVS


async def _get_company(db: AsyncSession, company_id: UUID, tenant_id: UUID) -> Company:
    company = (
        await db.execute(
            select(Company).where(Company.id == company_id, Company.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.post("/requests", response_model=CorporateRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_training_request(
    payload: CorporateRequestCreate,
    db: AsyncSession = Depends(get_db),
):
    """Public B2B lead capture for the currently resolved tenant."""
    tenant_id = get_current_tenant_id()
    request = CorporateTrainingRequest(
        tenant_id=tenant_id,
        company_name=payload.company_name.strip(),
        cnpj=_clean_cnpj(payload.cnpj),
        contact_name=payload.contact_name.strip(),
        contact_email=normalize_email(str(payload.contact_email)),
        contact_phone=payload.contact_phone,
        course_interest=payload.course_interest,
        employee_count=payload.employee_count,
        message=payload.message,
    )
    db.add(request)
    await db.commit()
    await db.refresh(request)
    return request


@router.get("/requests", response_model=list[CorporateRequestResponse])
async def list_training_requests(
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(CorporateTrainingRequest).where(CorporateTrainingRequest.tenant_id == tenant_id)
    if status_filter:
        stmt = stmt.where(CorporateTrainingRequest.status == status_filter.upper())
    result = await db.execute(stmt.order_by(CorporateTrainingRequest.created_at.desc()))
    return result.scalars().all()


@router.patch("/requests/{request_id}", response_model=CorporateRequestResponse)
async def update_training_request(
    request_id: UUID,
    payload: CorporateRequestUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    lead = (
        await db.execute(
            select(CorporateTrainingRequest).where(
                CorporateTrainingRequest.id == request_id,
                CorporateTrainingRequest.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Corporate request not found")
    data = payload.model_dump(exclude_unset=True)
    if data.get("status"):
        data["status"] = data["status"].upper()
        if data["status"] not in _REQUEST_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid corporate request status")
    for key, value in data.items():
        setattr(lead, key, value)
    await db.commit()
    await db.refresh(lead)
    return lead


@router.post("/companies/{company_id}/employees/link")
async def link_existing_employee(
    company_id: UUID,
    payload: CorporateLinkEmployeeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    company = await _get_company(db, company_id, tenant_id)
    if not payload.student_id and not payload.email:
        raise HTTPException(status_code=400, detail="student_id or email is required")

    stmt = select(Student).options(selectinload(Student.user)).where(Student.tenant_id == tenant_id)
    if payload.student_id:
        stmt = stmt.where(Student.id == payload.student_id)
    else:
        normalized = normalize_email(str(payload.email))
        stmt = stmt.join(User, Student.user_id == User.id).where(User.email == normalized)
    student = (await db.execute(stmt)).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if student.company_id and student.company_id != company_id:
        raise HTTPException(status_code=409, detail="Student is already linked to another company")

    student.company_id = company_id
    student.company = company.trade_name or company.legal_name
    await db.commit()
    return {"student_id": str(student.id), "company_id": str(company.id), "linked": True}


@router.post(
    "/companies/{company_id}/invites",
    response_model=CorporateInviteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_employee(
    company_id: UUID,
    payload: CorporateInviteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    company = await _get_company(db, company_id, tenant_id)
    email = normalize_email(str(payload.email))

    user = (
        await db.execute(select(User).where(User.tenant_id == tenant_id, User.email == email))
    ).scalar_one_or_none()
    student = None
    if user:
        student = (
            await db.execute(select(Student).where(Student.tenant_id == tenant_id, Student.user_id == user.id))
        ).scalar_one_or_none()
        if not student:
            raise HTTPException(status_code=409, detail="Existing user is not a student")
        if student.company_id and student.company_id != company_id:
            raise HTTPException(status_code=409, detail="Student belongs to another company")
        student.company_id = company_id
        student.company = company.trade_name or company.legal_name
    else:
        if not payload.full_name or not payload.cpf:
            raise HTTPException(status_code=400, detail="full_name and cpf are required for a new employee")
        try:
            cpf = validate_cpf(payload.cpf)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="CPF inválido") from exc
        duplicate_cpf = (
            await db.execute(select(User).where(User.tenant_id == tenant_id, User.cpf == cpf))
        ).scalar_one_or_none()
        if duplicate_cpf:
            raise HTTPException(status_code=409, detail="CPF already registered")
        user = User(
            tenant_id=tenant_id,
            email=email,
            cpf=cpf,
            full_name=payload.full_name.strip(),
            password_hash=None,
            role=UserRole.STUDENT,
            is_active=False,
        )
        db.add(user)
        await db.flush()
        student = Student(
            tenant_id=tenant_id,
            user_id=user.id,
            cpf=cpf,
            phone=payload.phone,
            company_id=company_id,
            company=company.trade_name or company.legal_name,
        )
        db.add(student)
        await db.flush()

    raw_token = None
    token_model = None
    invite_status = "ACCEPTED" if user.is_active else "PENDING"
    if not user.is_active:
        raw_token, token_model = await OneTimeTokenService.create(
            db, str(user.id), "activation", ttl_hours=168
        )

    invite = CorporateInvite(
        tenant_id=tenant_id,
        company_id=company_id,
        student_id=student.id,
        email=email,
        full_name=user.full_name,
        status=invite_status,
        token_id=token_model.id if token_model else None,
        invited_by=UUID(current_user["user_id"]),
        expires_at=token_model.expires_at if token_model else None,
        accepted_at=utc_now() if user.is_active else None,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)

    email_sent = False
    returned_token = raw_token if raw_token and _can_return_token() else None
    if raw_token and not _can_return_token():
        try:
            await get_email_service().send_account_activation(
                to=email,
                activation_token=raw_token,
                frontend_url=settings.FRONTEND_URL,
                tenant_name="Plataforma",
            )
            email_sent = True
        except EmailServiceError:
            pass

    return CorporateInviteResponse(
        id=invite.id,
        company_id=company_id,
        student_id=student.id,
        email=email,
        full_name=user.full_name,
        status=invite.status,
        expires_at=invite.expires_at,
        created_at=invite.created_at,
        activation_token=returned_token,
        activation_email_sent=email_sent,
    )


@router.post("/companies/{company_id}/employees/{student_id}/resend-activation", response_model=CorporateInviteResponse)
async def resend_employee_activation(
    company_id: UUID,
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _get_company(db, company_id, tenant_id)
    row = (
        await db.execute(
            select(Student, User)
            .join(User, Student.user_id == User.id)
            .where(
                Student.id == student_id,
                Student.company_id == company_id,
                Student.tenant_id == tenant_id,
            )
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Employee not found")
    student, user = row
    if user.is_active:
        raise HTTPException(status_code=409, detail="Account is already active")

    raw_token, token_model = await OneTimeTokenService.create(db, str(user.id), "activation", ttl_hours=168)
    invite = CorporateInvite(
        tenant_id=tenant_id,
        company_id=company_id,
        student_id=student.id,
        email=user.email,
        full_name=user.full_name,
        status="PENDING",
        token_id=token_model.id,
        invited_by=UUID(current_user["user_id"]),
        expires_at=token_model.expires_at,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)

    email_sent = False
    returned_token = raw_token if _can_return_token() else None
    if not _can_return_token():
        try:
            await get_email_service().send_account_activation(
                to=user.email,
                activation_token=raw_token,
                frontend_url=settings.FRONTEND_URL,
                tenant_name="Plataforma",
            )
            email_sent = True
        except EmailServiceError:
            pass

    return CorporateInviteResponse(
        id=invite.id,
        company_id=company_id,
        student_id=student.id,
        email=user.email,
        full_name=user.full_name,
        status=invite.status,
        expires_at=invite.expires_at,
        created_at=invite.created_at,
        activation_token=returned_token,
        activation_email_sent=email_sent,
    )


@router.post("/companies/{company_id}/employees/{student_id}/offboard")
async def offboard_employee(
    company_id: UUID,
    student_id: UUID,
    payload: CorporateOffboardRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _get_company(db, company_id, tenant_id)
    row = (
        await db.execute(
            select(Student, User)
            .join(User, Student.user_id == User.id)
            .where(
                Student.id == student_id,
                Student.company_id == company_id,
                Student.tenant_id == tenant_id,
            )
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Employee not found")
    student, user = row

    cancelled = 0
    if payload.cancel_active_corporate_enrollments:
        enrollments = (
            await db.execute(
                select(Enrollment).where(
                    Enrollment.tenant_id == tenant_id,
                    Enrollment.student_id == student.id,
                    Enrollment.source == EnrollmentSource.CORPORATE,
                    Enrollment.status.in_([EnrollmentStatus.PENDENTE, EnrollmentStatus.CONFIRMADA]),
                )
            )
        ).scalars().all()
        for enrollment in enrollments:
            enrollment.status = EnrollmentStatus.CANCELADA
            cancelled += 1

    student.company_id = None
    student.company = None
    if payload.deactivate_account:
        user.is_active = False
    await db.commit()
    return {
        "student_id": str(student.id),
        "company_id": str(company_id),
        "offboarded": True,
        "corporate_enrollments_cancelled": cancelled,
        "account_deactivated": bool(payload.deactivate_account),
    }


async def _seat_usage(db: AsyncSession, allocation: CorporateSeatAllocation) -> int:
    return int(
        await db.scalar(
            select(func.count(Enrollment.id))
            .join(Student, Enrollment.student_id == Student.id)
            .where(
                Enrollment.tenant_id == allocation.tenant_id,
                Enrollment.class_id == allocation.class_id,
                Enrollment.source == EnrollmentSource.CORPORATE,
                Enrollment.status != EnrollmentStatus.CANCELADA,
                Student.company_id == allocation.company_id,
            )
        )
        or 0
    )


@router.post("/companies/{company_id}/seat-allocations", response_model=CorporateSeatAllocationResponse)
async def upsert_seat_allocation(
    company_id: UUID,
    payload: CorporateSeatAllocationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _get_company(db, company_id, tenant_id)
    class_obj = (
        await db.execute(select(Class).where(Class.id == payload.class_id, Class.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found")
    if payload.seats_reserved > class_obj.max_students:
        raise HTTPException(status_code=409, detail="Reserved seats exceed class capacity")

    allocation = (
        await db.execute(
            select(CorporateSeatAllocation).where(
                CorporateSeatAllocation.tenant_id == tenant_id,
                CorporateSeatAllocation.company_id == company_id,
                CorporateSeatAllocation.class_id == payload.class_id,
            )
        )
    ).scalar_one_or_none()
    if allocation:
        used = await _seat_usage(db, allocation)
        if payload.seats_reserved < used:
            raise HTTPException(status_code=409, detail="Reserved seats cannot be lower than seats already used")
        allocation.seats_reserved = payload.seats_reserved
        allocation.expires_at = payload.expires_at
        allocation.notes = payload.notes
        allocation.is_active = True
    else:
        allocation = CorporateSeatAllocation(
            tenant_id=tenant_id,
            company_id=company_id,
            class_id=payload.class_id,
            seats_reserved=payload.seats_reserved,
            expires_at=payload.expires_at,
            notes=payload.notes,
            created_by=UUID(current_user["user_id"]),
        )
        db.add(allocation)
        await db.flush()
        used = 0
    await db.commit()
    await db.refresh(allocation)
    used = await _seat_usage(db, allocation)
    return CorporateSeatAllocationResponse(
        id=allocation.id,
        company_id=company_id,
        class_id=allocation.class_id,
        seats_reserved=allocation.seats_reserved,
        seats_used=used,
        seats_available=max(0, allocation.seats_reserved - used),
        is_active=allocation.is_active,
        expires_at=allocation.expires_at,
        notes=allocation.notes,
        created_at=allocation.created_at,
        updated_at=allocation.updated_at,
    )


@router.get("/companies/{company_id}/seat-allocations", response_model=list[CorporateSeatAllocationResponse])
async def list_seat_allocations(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _get_company(db, company_id, tenant_id)
    allocations = (
        await db.execute(
            select(CorporateSeatAllocation)
            .where(
                CorporateSeatAllocation.tenant_id == tenant_id,
                CorporateSeatAllocation.company_id == company_id,
            )
            .order_by(CorporateSeatAllocation.created_at.desc())
        )
    ).scalars().all()
    response = []
    for allocation in allocations:
        used = await _seat_usage(db, allocation)
        response.append(
            CorporateSeatAllocationResponse(
                id=allocation.id,
                company_id=company_id,
                class_id=allocation.class_id,
                seats_reserved=allocation.seats_reserved,
                seats_used=used,
                seats_available=max(0, allocation.seats_reserved - used),
                is_active=allocation.is_active,
                expires_at=allocation.expires_at,
                notes=allocation.notes,
                created_at=allocation.created_at,
                updated_at=allocation.updated_at,
            )
        )
    return response


@router.post("/companies/{company_id}/bulk-enroll", response_model=CorporateBulkEnrollResponse)
async def bulk_enroll_company_employees(
    company_id: UUID,
    payload: CorporateBulkEnrollRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    company = await _get_company(db, company_id, tenant_id)
    row = (
        await db.execute(
            select(Class, Course)
            .join(Course, Class.course_id == Course.id)
            .where(Class.id == payload.class_id, Class.tenant_id == tenant_id, Course.tenant_id == tenant_id)
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Class not found")
    class_obj, course = row
    if class_obj.status not in (ClassStatus.ABERTA, ClassStatus.EM_ANDAMENTO):
        raise HTTPException(status_code=409, detail="Class is not open for enrollment")

    unique_student_ids = list(dict.fromkeys(payload.student_ids))
    students = (
        await db.execute(
            select(Student).where(
                Student.tenant_id == tenant_id,
                Student.company_id == company_id,
                Student.id.in_(unique_student_ids),
            )
        )
    ).scalars().all()
    student_map = {student.id: student for student in students}

    existing_rows = (
        await db.execute(
            select(Enrollment).where(
                Enrollment.tenant_id == tenant_id,
                Enrollment.class_id == class_obj.id,
                Enrollment.student_id.in_(unique_student_ids),
            )
        )
    ).scalars().all()
    existing_by_student = {row.student_id: row for row in existing_rows}

    allocation = (
        await db.execute(
            select(CorporateSeatAllocation).where(
                CorporateSeatAllocation.tenant_id == tenant_id,
                CorporateSeatAllocation.company_id == company_id,
                CorporateSeatAllocation.class_id == class_obj.id,
                CorporateSeatAllocation.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()

    candidates = [sid for sid in unique_student_ids if sid in student_map and sid not in existing_by_student]
    current_class_count = int(
        await db.scalar(
            select(func.count(Enrollment.id)).where(
                Enrollment.tenant_id == tenant_id,
                Enrollment.class_id == class_obj.id,
                Enrollment.status != EnrollmentStatus.CANCELADA,
            )
        )
        or 0
    )
    if current_class_count + len(candidates) > class_obj.max_students:
        raise HTTPException(status_code=409, detail="Bulk enrollment exceeds class capacity")

    if allocation:
        if allocation.expires_at and allocation.expires_at <= utc_now():
            raise HTTPException(status_code=409, detail="Corporate seat allocation is expired")
        used = await _seat_usage(db, allocation)
        if used + len(candidates) > allocation.seats_reserved:
            raise HTTPException(status_code=409, detail="Bulk enrollment exceeds reserved corporate seats")

    created_ids: list[UUID] = []
    errors: list[str] = []
    rejected = 0
    for student_id in unique_student_ids:
        if student_id not in student_map:
            rejected += 1
            errors.append(f"Student {student_id} is not linked to company {company.id}")
            continue
        if student_id in existing_by_student:
            continue
        enrollment = Enrollment(
            tenant_id=tenant_id,
            student_id=student_id,
            class_id=class_obj.id,
            status=EnrollmentStatus.CONFIRMADA,
            source=EnrollmentSource.CORPORATE,
            price=course.price if payload.unit_price is None else payload.unit_price,
        )
        db.add(enrollment)
        await db.flush()
        created_ids.append(enrollment.id)

    batch = CorporateEnrollmentBatch(
        tenant_id=tenant_id,
        company_id=company_id,
        class_id=class_obj.id,
        enrollment_count=len(created_ids),
        created_by=UUID(current_user["user_id"]),
        created_by_name=current_user.get("full_name") or current_user.get("email"),
    )
    db.add(batch)
    await db.commit()

    return CorporateBulkEnrollResponse(
        batch_id=batch.id,
        requested=len(unique_student_ids),
        created=len(created_ids),
        existing=len(existing_by_student),
        rejected=rejected,
        enrollment_ids=created_ids,
        errors=errors,
    )


@router.get("/companies/{company_id}/training-report", response_model=CorporateTrainingReport)
async def company_training_report(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _get_company(db, company_id, tenant_id)
    students = (
        await db.execute(
            select(Student)
            .options(selectinload(Student.user))
            .where(Student.tenant_id == tenant_id, Student.company_id == company_id)
            .order_by(Student.created_at.desc())
        )
    ).scalars().all()

    rows: list[CorporateEmployeeReportRow] = []
    total_enrollments = 0
    active_enrollments = 0
    completed_enrollments = 0
    certificate_total = 0

    for student in students:
        enrollments = (
            await db.execute(
                select(Enrollment).where(
                    Enrollment.tenant_id == tenant_id,
                    Enrollment.student_id == student.id,
                )
            )
        ).scalars().all()
        enrollment_ids = [e.id for e in enrollments]
        certificates = 0
        if enrollment_ids:
            certificates = int(
                await db.scalar(
                    select(func.count(Certificate.id)).where(
                        Certificate.tenant_id == tenant_id,
                        Certificate.enrollment_id.in_(enrollment_ids),
                    )
                )
                or 0
            )
        active = sum(e.status in (EnrollmentStatus.PENDENTE, EnrollmentStatus.CONFIRMADA) for e in enrollments)
        completed = sum(e.status == EnrollmentStatus.CONCLUIDA for e in enrollments)
        total_enrollments += len(enrollments)
        active_enrollments += active
        completed_enrollments += completed
        certificate_total += certificates
        rows.append(
            CorporateEmployeeReportRow(
                student_id=student.id,
                full_name=student.full_name or "",
                email=student.email or "",
                active=bool(student.user_active),
                total_enrollments=len(enrollments),
                active_enrollments=active,
                completed_enrollments=completed,
                certificates=certificates,
            )
        )

    completion_rate = (
        round((completed_enrollments / total_enrollments) * 100, 2)
        if total_enrollments
        else 0.0
    )
    return CorporateTrainingReport(
        company_id=company_id,
        total_employees=len(students),
        total_enrollments=total_enrollments,
        active_enrollments=active_enrollments,
        completed_enrollments=completed_enrollments,
        certificates=certificate_total,
        completion_rate=completion_rate,
        employees=rows,
    )
