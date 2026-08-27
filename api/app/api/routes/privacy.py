from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id, get_current_user
from app.core.utils import utc_now
from app.models.certificate import Certificate
from app.models.class_model import Class
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.governance import PrivacyRequest
from app.models.payment import Payment
from app.models.student import Student
from app.models.user import User
from app.schemas.governance import (
    PrivacyRequestAdminUpdate,
    PrivacyRequestCreate,
    PrivacyRequestResponse,
)

router = APIRouter()
_REQUEST_TYPES = frozenset({"ACCESS", "EXPORT", "CORRECTION", "DELETION", "OBJECTION"})
_OPEN_STATUSES = frozenset({"OPEN", "IN_REVIEW"})
_ALLOWED_STATUSES = frozenset({"OPEN", "IN_REVIEW", "COMPLETED", "REJECTED"})


def _normalize_request_type(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in _REQUEST_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid privacy request type. Allowed: {', '.join(sorted(_REQUEST_TYPES))}",
        )
    return normalized


async def _commit_privacy_change(db: AsyncSession) -> None:
    """Commit privacy state while mapping the known uniqueness race to 409."""
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if "uq_privacy_request_open_type" in str(exc.orig):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An open privacy request of this type already exists",
            ) from exc
        raise


@router.post("/requests", response_model=PrivacyRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_privacy_request(
    payload: PrivacyRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Open a tenant-scoped data-subject request without destructive automation."""
    tenant_id = get_current_tenant_id()
    user_id = UUID(current_user["user_id"])
    request_type = _normalize_request_type(payload.request_type)

    existing = (
        await db.execute(
            select(PrivacyRequest).where(
                PrivacyRequest.tenant_id == tenant_id,
                PrivacyRequest.user_id == user_id,
                PrivacyRequest.request_type == request_type,
                PrivacyRequest.status.in_(_OPEN_STATUSES),
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An open privacy request of this type already exists",
        )

    privacy_request = PrivacyRequest(
        tenant_id=tenant_id,
        user_id=user_id,
        request_type=request_type,
        status="OPEN",
        details=payload.details.strip() if payload.details else None,
    )
    db.add(privacy_request)
    await _commit_privacy_change(db)
    await db.refresh(privacy_request)
    return privacy_request


@router.get("/requests/me", response_model=list[PrivacyRequestResponse])
async def list_my_privacy_requests(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    user_id = UUID(current_user["user_id"])
    return (
        await db.execute(
            select(PrivacyRequest)
            .where(
                PrivacyRequest.tenant_id == tenant_id,
                PrivacyRequest.user_id == user_id,
            )
            .order_by(PrivacyRequest.created_at.desc())
        )
    ).scalars().all()


@router.get("/requests", response_model=list[PrivacyRequestResponse])
async def list_privacy_requests(
    status_filter: str | None = None,
    request_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(PrivacyRequest).where(PrivacyRequest.tenant_id == tenant_id)
    if status_filter:
        normalized_status = status_filter.strip().upper()
        if normalized_status not in _ALLOWED_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid privacy request status")
        stmt = stmt.where(PrivacyRequest.status == normalized_status)
    if request_type:
        stmt = stmt.where(PrivacyRequest.request_type == _normalize_request_type(request_type))
    return (await db.execute(stmt.order_by(PrivacyRequest.created_at.desc()))).scalars().all()


@router.patch("/requests/{request_id}", response_model=PrivacyRequestResponse)
async def update_privacy_request(
    request_id: UUID,
    payload: PrivacyRequestAdminUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Review/close a request. No account or learning history is deleted here."""
    tenant_id = get_current_tenant_id()
    privacy_request = (
        await db.execute(
            select(PrivacyRequest).where(
                PrivacyRequest.id == request_id,
                PrivacyRequest.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not privacy_request:
        raise HTTPException(status_code=404, detail="Privacy request not found")

    new_status = payload.status.strip().upper()
    if new_status not in _ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid privacy request status")

    privacy_request.status = new_status
    privacy_request.admin_notes = payload.admin_notes.strip() if payload.admin_notes else None
    if new_status in {"COMPLETED", "REJECTED"}:
        privacy_request.resolved_by = UUID(current_user["user_id"])
        privacy_request.resolved_at = utc_now()
    else:
        privacy_request.resolved_by = None
        privacy_request.resolved_at = None

    await _commit_privacy_change(db)
    await db.refresh(privacy_request)
    return privacy_request


@router.get("/me/export")
async def export_my_personal_data(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return a tenant-scoped machine-readable copy of the caller's core data.

    This endpoint is intentionally read-only and excludes secrets, password
    hashes, auth tokens and other users' information.
    """
    tenant_id = get_current_tenant_id()
    user_id = UUID(current_user["user_id"])
    user = (
        await db.execute(
            select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    student = (
        await db.execute(
            select(Student).where(Student.user_id == user_id, Student.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()

    enrollments: list[Enrollment] = []
    course_by_class: dict[UUID, Course] = {}
    certificates: list[Certificate] = []
    payments: list[Payment] = []
    if student:
        enrollments = (
            await db.execute(
                select(Enrollment)
                .where(Enrollment.student_id == student.id, Enrollment.tenant_id == tenant_id)
                .order_by(Enrollment.created_at.asc())
            )
        ).scalars().all()
        class_ids = {item.class_id for item in enrollments}
        if class_ids:
            rows = (
                await db.execute(
                    select(Class, Course)
                    .join(Course, Class.course_id == Course.id)
                    .where(
                        Class.id.in_(class_ids),
                        Class.tenant_id == tenant_id,
                        Course.tenant_id == tenant_id,
                    )
                )
            ).all()
            course_by_class = {class_obj.id: course for class_obj, course in rows}

        enrollment_ids = [item.id for item in enrollments]
        if enrollment_ids:
            certificates = (
                await db.execute(
                    select(Certificate)
                    .where(
                        Certificate.tenant_id == tenant_id,
                        Certificate.enrollment_id.in_(enrollment_ids),
                    )
                    .order_by(Certificate.issued_at.asc())
                )
            ).scalars().all()
            payments = (
                await db.execute(
                    select(Payment)
                    .where(
                        Payment.tenant_id == tenant_id,
                        Payment.enrollment_id.in_(enrollment_ids),
                    )
                    .order_by(Payment.created_at.asc())
                )
            ).scalars().all()

    def enum_value(value):
        return getattr(value, "value", value)

    return {
        "generated_at": utc_now().isoformat(),
        "tenant_id": str(tenant_id),
        "account": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "cpf": user.cpf,
            "role": enum_value(user.role),
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "student_profile": (
            {
                "id": str(student.id),
                "cpf": student.cpf,
                "phone": student.phone,
                "company_id": str(student.company_id) if student.company_id else None,
                "company": student.company,
                "address": student.address,
                "city": student.city,
                "state": student.state,
                "zip_code": student.zip_code,
                "created_at": student.created_at.isoformat() if student.created_at else None,
            }
            if student
            else None
        ),
        "enrollments": [
            {
                "id": str(item.id),
                "class_id": str(item.class_id),
                "course_id": (
                    str(course_by_class[item.class_id].id)
                    if item.class_id in course_by_class
                    else None
                ),
                "course_name": (
                    course_by_class[item.class_id].name
                    if item.class_id in course_by_class
                    else None
                ),
                "status": enum_value(item.status),
                "source": enum_value(item.source),
                "price": item.price,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in enrollments
        ],
        "certificates": [
            {
                "id": str(item.id),
                "enrollment_id": str(item.enrollment_id),
                "certificate_number": item.certificate_number,
                "validation_code": item.validation_code,
                "status": enum_value(getattr(item, "status", None)),
                "issued_at": item.issued_at.isoformat() if item.issued_at else None,
                "expires_at": item.expires_at.isoformat() if getattr(item, "expires_at", None) else None,
            }
            for item in certificates
        ],
        "payments": [
            {
                "id": str(item.id),
                "enrollment_id": str(item.enrollment_id) if item.enrollment_id else None,
                "amount": item.amount,
                "status": enum_value(item.status),
                "method": enum_value(item.method),
                "provider": enum_value(item.provider),
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "paid_at": item.paid_at.isoformat() if item.paid_at else None,
            }
            for item in payments
        ],
    }
