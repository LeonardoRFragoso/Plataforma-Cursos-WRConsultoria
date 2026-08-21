import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id, get_current_user
from app.models.certificate import Certificate
from app.models.class_model import Class
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.student import Student
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.certificate import (
    CertificateCreate,
    CertificateResponse,
    CertificateValidationRequest,
    CertificateValidationResponse,
    StudentCertificateResponse,
)
from app.services.certificate_service import CertificateService

router = APIRouter()

def generate_certificate_number() -> str:
    return f"CERT-{uuid.uuid4().hex[:12].upper()}"

def generate_validation_code() -> str:
    return f"{uuid.uuid4().hex[:16].upper()}"


def _resolve_trusted_frontend_url(request: Request, tenant: Tenant | None) -> str:
    """Derive the validation frontend URL from the trusted request Origin.

    The tenant middleware already validates the Origin header against
    TRUSTED_FRONTEND_ORIGINS in staging/production. If the Origin is
    present and matches a trusted origin, use it for the validation URL
    so certificates point to the correct tenant frontend.

    Falls back to settings.FRONTEND_URL when Origin is absent or untrusted
    (e.g. API-only requests without a browser Origin header).
    """
    origin = request.headers.get("origin")
    if origin:
        origin = origin.strip().rstrip("/")
    if origin and origin in {
        o.strip().rstrip("/") for o in getattr(settings, "TRUSTED_FRONTEND_ORIGINS", []) if o
    }:
        return origin
    return settings.FRONTEND_URL


async def _load_certificate_with_tenant(
    db: AsyncSession, certificate_id: UUID, tenant_id: UUID | None = None
):
    """Load certificate joined to enrollment, student, user, class, course, tenant.

    When tenant_id is provided, the query is filtered by
    Certificate.tenant_id == tenant_id so cross-tenant certificates
    are never loaded (defense in depth at the DB layer).

    Returns (certificate, enrollment, student, user, class_obj, course, tenant) or None.
    """
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
    result = await db.execute(stmt)
    return result.first()


def _authorize_certificate_access(
    certificate: Certificate,
    user: User,
    current_user: dict,
    resolved_tenant_id: UUID,
) -> None:
    """Shared authorization for certificate get/download/delete.

    Contract (applies to ALL roles including SUPER_ADMIN):
    - ADMIN/SUPER_ADMIN: allowed only if certificate.tenant_id == resolved_tenant_id.
    - STUDENT: allowed only if certificate belongs to them AND tenant matches.
    - Other student same tenant: 403.
    - Cross-tenant (any role): 404 (non-disclosing).

    SUPER_ADMIN behaves as a tenant admin on regular /certificates routes.
    Global certificate management must use explicit /super-admin/ routes.

    Raises HTTPException if unauthorized.
    """
    is_admin = current_user.get("role") in ("admin", "super_admin")
    is_owner = str(user.id) == current_user["user_id"]

    # Cross-tenant: return 404 (non-disclosing) to avoid leaking existence.
    # No role bypasses this — including SUPER_ADMIN.
    if certificate.tenant_id != resolved_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found",
        )

    if is_admin:
        return

    if is_owner:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Cannot access this certificate",
    )


@router.post("/", response_model=CertificateResponse, status_code=status.HTTP_201_CREATED)
async def create_certificate(
    cert_data: CertificateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()

    # Load enrollment joined to class and course to verify tenant ownership.
    stmt = (
        select(Enrollment, Class, Course)
        .join(Class, Enrollment.class_id == Class.id)
        .join(Course, Class.course_id == Course.id)
        .where(Enrollment.id == cert_data.enrollment_id)
    )
    result = await db.execute(stmt)
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found",
        )

    _enrollment, _class, course = row

    # Defense in depth: verify enrollment belongs to the resolved tenant
    # via the course's tenant_id. Do not trust enrollment_id alone.
    if course.tenant_id != tenant_id:
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
        tenant_id=tenant_id,
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
    tenant_id = get_current_tenant_id()
    stmt = (
        select(Certificate)
        .where(Certificate.tenant_id == tenant_id)
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    certificates = result.scalars().all()
    return certificates


@router.get("/me", response_model=list[StudentCertificateResponse])
async def list_my_certificates(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return the authenticated student's certificates with course context.

    Students only. Admins/super_admins get an empty list (they use the
    tenant-scoped GET /). The query is filtered at the DB layer by both
    the resolved tenant_id and the student's own user_id, so cross-tenant
    and cross-student certificates are never loaded.
    """
    if current_user.get("role") != "student":
        return []

    tenant_id = get_current_tenant_id()
    user_id = UUID(current_user["user_id"])

    stmt = (
        select(Certificate, Enrollment, Student, Class, Course)
        .join(Enrollment, Certificate.enrollment_id == Enrollment.id)
        .join(Student, Enrollment.student_id == Student.id)
        .join(Class, Enrollment.class_id == Class.id)
        .join(Course, Class.course_id == Course.id)
        .where(
            Certificate.tenant_id == tenant_id,
            Student.user_id == user_id,
        )
        .order_by(Certificate.issued_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        StudentCertificateResponse(
            id=certificate.id,
            enrollment_id=certificate.enrollment_id,
            certificate_number=certificate.certificate_number,
            validation_code=certificate.validation_code,
            issued_at=certificate.issued_at,
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


@router.get("/{certificate_id}", response_model=CertificateResponse)
async def get_certificate(
    certificate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()

    # For students, load with full context to verify ownership.
    # DB-layer tenant filter ensures cross-tenant certs are never loaded.
    if current_user.get("role") == "student":
        row = await _load_certificate_with_tenant(db, certificate_id, tenant_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Certificate not found",
            )
        certificate, _enrollment, _student, user, _class, _course, _tenant = row
        _authorize_certificate_access(certificate, user, current_user, tenant_id)
        return certificate

    # Admins: tenant-filtered query (no need to load joins).
    stmt = select(Certificate).where(
        Certificate.id == certificate_id,
        Certificate.tenant_id == tenant_id,
    )
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

@router.get("/{certificate_id}/download")
async def download_certificate(
    certificate_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    # DB-layer tenant filter: cross-tenant certificates are never loaded.
    row = await _load_certificate_with_tenant(db, certificate_id, tenant_id)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found",
        )

    certificate, _enrollment, _student, user, class_obj, course, tenant = row

    # Defense in depth: re-check tenant boundary in memory.
    _authorize_certificate_access(certificate, user, current_user, tenant_id)

    admin_result = await db.execute(
        select(User).where(User.id == class_obj.responsible_admin_id)
    )
    admin = admin_result.scalar_one_or_none()
    responsible_admin_name = admin.full_name if admin else "Administrador"

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
        responsible_admin_name=responsible_admin_name,
        brand_name=tenant.name,
        validation_url=validation_url,
        issued_date=certificate.issued_at,
        brand_primary_color=tenant.primary_color,
        brand_logo_url=tenant.logo_url,
    )

    filename = f"certificate-{certificate.certificate_number}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

@router.delete("/{certificate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_certificate(
    certificate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(Certificate).where(
        Certificate.id == certificate_id,
        Certificate.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    certificate = result.scalar_one_or_none()

    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found",
        )

    await db.delete(certificate)
    await db.commit()
