from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes import certificates as legacy
from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id, get_current_user
from app.models.certificate import Certificate
from app.models.class_model import Class
from app.models.compliance import CourseComplianceProfile, TrainingProfessional
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.student import Student
from app.schemas.certificate import CertificateCreate, CertificateResponse, CertificateValidationRequest, CertificateValidationResponse
from app.services.certificate_service import is_demo_certificate
from app.services.certificate_storage import verify_certificate_pdf
from app.services.compliance_service import ComplianceService

router = APIRouter()


async def _regulated_context(db: AsyncSession, *, tenant_id: UUID, enrollment_id: UUID):
    row = (
        await db.execute(
            select(Enrollment, Student, Class, Course)
            .join(Student, Enrollment.student_id == Student.id)
            .join(Class, Enrollment.class_id == Class.id)
            .join(Course, Class.course_id == Course.id)
            .where(
                Enrollment.id == enrollment_id,
                Enrollment.tenant_id == tenant_id,
                Student.tenant_id == tenant_id,
                Class.tenant_id == tenant_id,
                Course.tenant_id == tenant_id,
            )
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    return row


@router.post("/", response_model=CertificateResponse, status_code=status.HTTP_201_CREATED)
async def guarded_create_certificate(
    cert_data: CertificateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Prevent an admin from bypassing NR regulatory completion rules.

    Non-regulated courses keep the existing behavior. NR/compliance-managed
    courses are fail-closed until every P0 regulatory prerequisite is proven.
    The cryptographic PAdES signing adapter is a separate launch gate and we
    never fabricate a signature while it is absent.
    """
    tenant_id = get_current_tenant_id()
    enrollment, student, _class_obj, course = await _regulated_context(
        db, tenant_id=tenant_id, enrollment_id=cert_data.enrollment_id
    )
    profile = (
        await db.execute(
            select(CourseComplianceProfile).where(
                CourseComplianceProfile.tenant_id == tenant_id,
                CourseComplianceProfile.course_id == course.id,
            )
        )
    ).scalar_one_or_none()
    is_regulated = course.code.upper().startswith("NR-") or profile is not None
    if not is_regulated:
        return await legacy.create_certificate(cert_data, db, current_user)

    if enrollment.status != EnrollmentStatus.CONCLUIDA:
        raise HTTPException(status_code=409, detail="Certificate requires a completed enrollment")

    readiness = await ComplianceService.official_issuance_readiness(
        db,
        tenant_id=tenant_id,
        enrollment=enrollment,
        course_id=course.id,
        student_id=student.id,
    )
    if not readiness.ready:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Emissão oficial bloqueada por requisitos regulatórios pendentes",
                "issues": readiness.issues,
            },
        )

    technical = (
        await db.execute(
            select(TrainingProfessional).where(
                TrainingProfessional.id == profile.technical_responsible_id,
                TrainingProfessional.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not technical or technical.signature_method != "PADES_ICP_BRASIL":
        raise HTTPException(
            status_code=409,
            detail="Emissão oficial requer assinatura PAdES/ICP-Brasil configurada para o responsável técnico",
        )

    # Important: never create a visually signed-but-cryptographically-unsigned
    # NR certificate. The signing adapter is intentionally a separate gate.
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Emissão oficial preparada, aguardando integração do assinador PAdES/ICP-Brasil",
    )


@router.post("/validate", response_model=CertificateValidationResponse)
async def guarded_public_validation(
    payload: CertificateValidationRequest,
    db: AsyncSession = Depends(get_db),
):
    response = await legacy.validate_certificate(payload, db)
    if not response.valid or response.is_demo:
        return response

    certificate = (
        await db.execute(
            select(Certificate).where(Certificate.validation_code == payload.validation_code)
        )
    ).scalar_one_or_none()
    if certificate and (
        not certificate.snapshot_json
        or not certificate.pdf_storage_key
        or not certificate.pdf_sha256
        or certificate.signature_status != "SIGNED"
    ):
        # Legacy certificates remain auditable but are not represented as
        # regulatorily trusted until migrated/reissued with immutable evidence.
        response.valid = False
        response.status = "COMPLIANCE_REVIEW_REQUIRED"
    return response


@router.get("/{certificate_id}/download")
async def guarded_download_certificate(
    certificate_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    row = await legacy._certificate_context(db, certificate_id, tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="Certificate not found")
    certificate, _enrollment, _student, user, _class_obj, _course, _tenant = row
    legacy._authorize(certificate, user, current_user, tenant_id)
    effective = legacy._effective_status(certificate)
    if effective != "ACTIVE":
        raise HTTPException(status_code=409, detail=f"Certificate is {effective.lower()}")

    if is_demo_certificate(certificate):
        return await legacy.download_certificate(certificate_id, request, db, current_user)

    if not certificate.pdf_storage_key or not certificate.pdf_sha256:
        raise HTTPException(
            status_code=409,
            detail="Certificado legado sem artefato imutável; requer revisão/reemissão",
        )
    if certificate.signature_status != "SIGNED":
        raise HTTPException(status_code=409, detail="Certificado ainda não possui assinatura oficial válida")

    pdf = await verify_certificate_pdf(
        storage_key=certificate.pdf_storage_key,
        expected_sha256=certificate.pdf_sha256,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=certificate-{certificate.certificate_number}.pdf"},
    )
