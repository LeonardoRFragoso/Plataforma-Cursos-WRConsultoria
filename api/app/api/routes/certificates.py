import hashlib
import uuid
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id, get_current_user
from app.core.utils import utc_now
from app.models.certificate import Certificate, CertificateEvent
from app.models.class_model import Class
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.student import Student
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.certificate import (
    CertificateCreate,
    CertificateEventResponse,
    CertificateReissueRequest,
    CertificateResponse,
    CertificateRevokeRequest,
    CertificateValidationRequest,
    CertificateValidationResponse,
    StudentCertificateResponse,
)
from app.services.certificate_service import CertificateService

router = APIRouter()


def generate_certificate_number() -> str:
    return f"CERT-{uuid.uuid4().hex[:12].upper()}"


def generate_validation_code() -> str:
    return uuid.uuid4().hex[:16].upper()


def _effective_status(certificate: Certificate) -> str:
    if certificate.status == "REVOKED":
        return "REVOKED"
    if certificate.status == "SUPERSEDED":
        return "SUPERSEDED"
    if certificate.expires_at and certificate.expires_at <= utc_now():
        return "EXPIRED"
    return "ACTIVE"


def _resolve_trusted_frontend_url(request: Request, tenant: Tenant | None) -> str:
    origin = request.headers.get("origin")
    if origin:
        origin = origin.strip().rstrip("/")
    trusted = {
        item.strip().rstrip("/")
        for item in getattr(settings, "TRUSTED_FRONTEND_ORIGINS", [])
        if item
    }
    return origin if origin and origin in trusted else settings.FRONTEND_URL


async def _certificate_context(db: AsyncSession, certificate_id: UUID, tenant_id: UUID | None = None):
    stmt = (
        select(Certificate, Enrollment, Student, User, Class, Course, Tenant)
        .join(Enrollment, Certificate.enrollment_id == Enrollment.id)
        .join(Student, Enrollment.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .join(Class, Enrollment.class_id == Class.id)
        .join(Course, Class.course_id == Course.id)
        .join(Tenant, Certificate.tenant_id == Tenant.id)
        .where(Certificate.id == certificate_id)
    )
    if tenant_id is not None:
        stmt = stmt.where(Certificate.tenant_id == tenant_id)
    return (await db.execute(stmt)).first()


def _authorize(certificate: Certificate, user: User, current_user: dict, tenant_id: UUID) -> None:
    if certificate.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if current_user.get("role") in ("admin", "super_admin"):
        return
    if str(user.id) == current_user["user_id"]:
        return
    raise HTTPException(status_code=403, detail="Cannot access this certificate")


def _content_hash(
    *,
    certificate_number: str,
    tenant_id: UUID,
    enrollment_id: UUID,
    student_id: UUID,
    course_id: UUID,
    issued_at,
    version: int,
) -> str:
    payload = "|".join(
        [
            certificate_number,
            str(tenant_id),
            str(enrollment_id),
            str(student_id),
            str(course_id),
            issued_at.isoformat(),
            str(version),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _issue_certificate(
    db: AsyncSession,
    *,
    enrollment: Enrollment,
    student: Student,
    course: Course,
    tenant_id: UUID,
    actor_id: UUID | None,
    supersedes_id: UUID | None = None,
    reason: str | None = None,
) -> Certificate:
    max_version = await db.scalar(
        select(func.coalesce(func.max(Certificate.version), 0)).where(
            Certificate.tenant_id == tenant_id,
            Certificate.enrollment_id == enrollment.id,
        )
    )
    version = int(max_version or 0) + 1
    issued_at = utc_now()
    expires_at = (
        issued_at + timedelta(days=course.certificate_validity_days)
        if course.certificate_validity_days
        else None
    )
    certificate = Certificate(
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
        certificate_number=generate_certificate_number(),
        validation_code=generate_validation_code(),
        issued_at=issued_at,
        expires_at=expires_at,
        status="ACTIVE",
        version=version,
        supersedes_id=supersedes_id,
    )
    certificate.content_hash = _content_hash(
        certificate_number=certificate.certificate_number,
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
        student_id=student.id,
        course_id=course.id,
        issued_at=issued_at,
        version=version,
    )
    db.add(certificate)
    await db.flush()
    db.add(
        CertificateEvent(
            tenant_id=tenant_id,
            certificate_id=certificate.id,
            event_type="REISSUED" if supersedes_id else "ISSUED",
            actor_id=actor_id,
            reason=reason,
            details=f"version={version};hash={certificate.content_hash}",
        )
    )
    return certificate


@router.post("/", response_model=CertificateResponse, status_code=status.HTTP_201_CREATED)
async def create_certificate(
    cert_data: CertificateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    row = (
        await db.execute(
            select(Enrollment, Student, Class, Course)
            .join(Student, Enrollment.student_id == Student.id)
            .join(Class, Enrollment.class_id == Class.id)
            .join(Course, Class.course_id == Course.id)
            .where(
                Enrollment.id == cert_data.enrollment_id,
                Enrollment.tenant_id == tenant_id,
                Student.tenant_id == tenant_id,
                Course.tenant_id == tenant_id,
            )
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    enrollment, student, _class, course = row
    if enrollment.status != EnrollmentStatus.CONCLUIDA:
        raise HTTPException(status_code=409, detail="Certificate requires a completed enrollment")

    active = (
        await db.execute(
            select(Certificate).where(
                Certificate.tenant_id == tenant_id,
                Certificate.enrollment_id == enrollment.id,
                Certificate.status == "ACTIVE",
            )
        )
    ).scalar_one_or_none()
    if active and _effective_status(active) == "ACTIVE":
        raise HTTPException(status_code=409, detail="Active certificate already exists for this enrollment")
    if active and _effective_status(active) == "EXPIRED":
        active.status = "SUPERSEDED"

    certificate = await _issue_certificate(
        db,
        enrollment=enrollment,
        student=student,
        course=course,
        tenant_id=tenant_id,
        actor_id=UUID(current_user["user_id"]),
        supersedes_id=active.id if active else None,
        reason="automatic renewal after expiry" if active else None,
    )
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
    tenant_id = get_current_tenant_id()
    result = await db.execute(
        select(Certificate)
        .where(Certificate.tenant_id == tenant_id)
        .order_by(Certificate.issued_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/me", response_model=list[StudentCertificateResponse])
async def list_my_certificates(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "student":
        return []
    tenant_id = get_current_tenant_id()
    user_id = UUID(current_user["user_id"])
    rows = (
        await db.execute(
            select(Certificate, Enrollment, Student, Class, Course)
            .join(Enrollment, Certificate.enrollment_id == Enrollment.id)
            .join(Student, Enrollment.student_id == Student.id)
            .join(Class, Enrollment.class_id == Class.id)
            .join(Course, Class.course_id == Course.id)
            .where(Certificate.tenant_id == tenant_id, Student.user_id == user_id)
            .order_by(Certificate.issued_at.desc())
        )
    ).all()
    return [
        StudentCertificateResponse(
            id=certificate.id,
            enrollment_id=certificate.enrollment_id,
            certificate_number=certificate.certificate_number,
            validation_code=certificate.validation_code,
            issued_at=certificate.issued_at,
            expires_at=certificate.expires_at,
            status=_effective_status(certificate),
            version=certificate.version,
            revocation_reason=certificate.revocation_reason,
            course_id=course.id,
            course_name=course.name,
            course_code=course.code,
            course_category=course.category,
            cover_image_url=course.cover_image_url,
            cover_image_alt=course.cover_image_alt,
            created_at=certificate.created_at,
            updated_at=certificate.updated_at,
        )
        for certificate, _enrollment, _student, _class, course in rows
    ]


@router.post("/validate", response_model=CertificateValidationResponse)
async def validate_certificate(
    payload: CertificateValidationRequest,
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(
            select(Certificate, Enrollment, Student, User, Class, Course)
            .join(Enrollment, Certificate.enrollment_id == Enrollment.id)
            .join(Student, Enrollment.student_id == Student.id)
            .join(User, Student.user_id == User.id)
            .join(Class, Enrollment.class_id == Class.id)
            .join(Course, Class.course_id == Course.id)
            .where(Certificate.validation_code == payload.validation_code)
        )
    ).first()
    if not row:
        return CertificateValidationResponse(valid=False, status="NOT_FOUND")
    certificate, _enrollment, _student, user, _class, course = row
    effective = _effective_status(certificate)
    return CertificateValidationResponse(
        valid=effective == "ACTIVE",
        status=effective,
        certificate_number=certificate.certificate_number,
        validation_code=certificate.validation_code,
        version=certificate.version,
        student_name=user.full_name,
        course_name=course.name,
        issued_at=certificate.issued_at,
        expires_at=certificate.expires_at,
        revoked_at=certificate.revoked_at,
        revocation_reason=certificate.revocation_reason,
        content_hash=certificate.content_hash,
    )


@router.get("/{certificate_id}", response_model=CertificateResponse)
async def get_certificate(
    certificate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    row = await _certificate_context(db, certificate_id, tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="Certificate not found")
    certificate, _enrollment, _student, user, _class, _course, _tenant = row
    _authorize(certificate, user, current_user, tenant_id)
    return certificate


@router.get("/{certificate_id}/history", response_model=list[CertificateEventResponse])
async def certificate_history(
    certificate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    certificate = (
        await db.execute(
            select(Certificate).where(Certificate.id == certificate_id, Certificate.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")
    events = (
        await db.execute(
            select(CertificateEvent)
            .where(
                CertificateEvent.tenant_id == tenant_id,
                CertificateEvent.certificate_id == certificate_id,
            )
            .order_by(CertificateEvent.created_at.desc())
        )
    ).scalars().all()
    return events


@router.post("/{certificate_id}/revoke", response_model=CertificateResponse)
async def revoke_certificate(
    certificate_id: UUID,
    payload: CertificateRevokeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    certificate = (
        await db.execute(
            select(Certificate).where(Certificate.id == certificate_id, Certificate.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if certificate.status == "REVOKED":
        return certificate
    if certificate.status == "SUPERSEDED":
        raise HTTPException(status_code=409, detail="Superseded certificate is already inactive")
    certificate.status = "REVOKED"
    certificate.revoked_at = utc_now()
    certificate.revoked_by = UUID(current_user["user_id"])
    certificate.revocation_reason = payload.reason.strip()
    db.add(
        CertificateEvent(
            tenant_id=tenant_id,
            certificate_id=certificate.id,
            event_type="REVOKED",
            actor_id=certificate.revoked_by,
            reason=certificate.revocation_reason,
        )
    )
    await db.commit()
    await db.refresh(certificate)
    return certificate


@router.post("/{certificate_id}/reissue", response_model=CertificateResponse, status_code=status.HTTP_201_CREATED)
async def reissue_certificate(
    certificate_id: UUID,
    payload: CertificateReissueRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    row = await _certificate_context(db, certificate_id, tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="Certificate not found")
    old, enrollment, student, _user, _class, course, _tenant = row
    if enrollment.status != EnrollmentStatus.CONCLUIDA:
        raise HTTPException(status_code=409, detail="Enrollment is not completed")
    if old.status == "SUPERSEDED":
        raise HTTPException(status_code=409, detail="Certificate was already superseded")

    active_replacement = (
        await db.execute(
            select(Certificate).where(
                Certificate.tenant_id == tenant_id,
                Certificate.enrollment_id == enrollment.id,
                Certificate.status == "ACTIVE",
                Certificate.id != old.id,
            )
        )
    ).scalar_one_or_none()
    if active_replacement:
        raise HTTPException(
            status_code=409,
            detail="An active replacement certificate already exists for this enrollment",
        )

    if old.status == "ACTIVE":
        old.status = "SUPERSEDED"
        old.revoked_at = utc_now()
        old.revoked_by = UUID(current_user["user_id"])
        old.revocation_reason = f"Superseded: {payload.reason.strip()}"
        db.add(
            CertificateEvent(
                tenant_id=tenant_id,
                certificate_id=old.id,
                event_type="SUPERSEDED",
                actor_id=old.revoked_by,
                reason=payload.reason.strip(),
            )
        )
    certificate = await _issue_certificate(
        db,
        enrollment=enrollment,
        student=student,
        course=course,
        tenant_id=tenant_id,
        actor_id=UUID(current_user["user_id"]),
        supersedes_id=old.id,
        reason=payload.reason.strip(),
    )
    await db.commit()
    await db.refresh(certificate)
    return certificate


@router.get("/{certificate_id}/download")
async def download_certificate(
    certificate_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    row = await _certificate_context(db, certificate_id, tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="Certificate not found")
    certificate, _enrollment, _student, user, class_obj, course, tenant = row
    _authorize(certificate, user, current_user, tenant_id)
    effective = _effective_status(certificate)
    if effective != "ACTIVE":
        raise HTTPException(status_code=409, detail=f"Certificate is {effective.lower()}")

    admin = (
        await db.execute(select(User).where(User.id == class_obj.responsible_admin_id))
    ).scalar_one_or_none()
    validation_url = (
        f"{_resolve_trusted_frontend_url(request, tenant)}"
        f"/certificates/validate?code={certificate.validation_code}"
    )
    pdf = CertificateService.generate_certificate_pdf(
        student_name=user.full_name,
        course_name=course.name,
        course_code=course.code,
        carga_horaria=course.carga_horaria,
        certificate_number=certificate.certificate_number,
        validation_code=certificate.validation_code,
        responsible_admin_name=admin.full_name if admin else "Administrador",
        brand_name=tenant.name,
        validation_url=validation_url,
        issued_date=certificate.issued_at,
        brand_primary_color=tenant.primary_color,
        brand_logo_url=tenant.logo_url,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=certificate-{certificate.certificate_number}.pdf"},
    )


@router.delete("/{certificate_id}", status_code=status.HTTP_409_CONFLICT)
async def delete_certificate(
    certificate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Trusted certificates are immutable records; use revoke/reissue instead."""
    tenant_id = get_current_tenant_id()
    certificate = (
        await db.execute(
            select(Certificate).where(
                Certificate.id == certificate_id,
                Certificate.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Certificates are immutable. Use the revoke or reissue lifecycle.",
    )
