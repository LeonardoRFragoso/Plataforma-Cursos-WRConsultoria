from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes import certificate_documents as document_routes
from app.api.routes import certificates as legacy_certificates
from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id, get_current_user
from app.core.utils import utc_now
from app.models.certificate import Certificate, CertificateEvent
from app.models.certificate_document import CertificateDocument
from app.models.class_model import Class
from app.models.compliance import CourseComplianceProfile
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.student import Student
from app.models.user import User
from app.schemas.certificate import (
    CertificateReissueRequest,
    CertificateResponse,
    CertificateValidationRequest,
    CertificateValidationResponse,
    StudentCertificateResponse,
)
from app.services.certificate_document_service import CertificateDocumentService
from app.services.certificate_service import is_demo_certificate

router = APIRouter(include_in_schema=False)


@router.post(
    "/certificates/validate",
    response_model=CertificateValidationResponse,
)
async def guarded_validate_certificate(
    payload: CertificateValidationRequest,
    db: AsyncSession = Depends(get_db),
):
    certificate = (
        await db.execute(
            select(Certificate).where(
                Certificate.validation_code == payload.validation_code
            )
        )
    ).scalar_one_or_none()
    if certificate and certificate.status == "PENDING_SIGNATURE":
        # Pending artifacts are not public credentials yet. Do not expose the
        # holder/course payload until a signing provider activates the record.
        return CertificateValidationResponse(
            valid=False,
            status="PENDING_SIGNATURE",
            is_demo=is_demo_certificate(certificate),
        )
    return await legacy_certificates.validate_certificate(payload=payload, db=db)


@router.get(
    "/certificates/me",
    response_model=list[StudentCertificateResponse],
)
async def guarded_list_my_certificates(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    response = await legacy_certificates.list_my_certificates(
        db=db,
        current_user=current_user,
    )
    if not response or current_user.get("role") != "student":
        return response
    tenant_id = get_current_tenant_id()
    pending_ids = set(
        (
            await db.execute(
                select(Certificate.id).where(
                    Certificate.tenant_id == tenant_id,
                    Certificate.status == "PENDING_SIGNATURE",
                    Certificate.id.in_([item.id for item in response]),
                )
            )
        ).scalars().all()
    )
    for item in response:
        if item.id in pending_ids:
            item.status = "PENDING_SIGNATURE"
    return response


@router.get("/certificates/{certificate_id}/download")
async def guarded_download_certificate(
    certificate_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    document = (
        await db.execute(
            select(CertificateDocument).where(
                CertificateDocument.tenant_id == tenant_id,
                CertificateDocument.certificate_id == certificate_id,
            )
        )
    ).scalar_one_or_none()
    if document:
        # The trusted path always returns persisted bytes. Never regenerate a
        # signed certificate at download time.
        return await document_routes._download(
            certificate_id=certificate_id,
            original=False,
            db=db,
            current_user=current_user,
        )
    return await legacy_certificates.download_certificate(
        certificate_id=certificate_id,
        request=request,
        db=db,
        current_user=current_user,
    )


@router.post(
    "/certificates/{certificate_id}/reissue",
    response_model=CertificateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def guarded_reissue_certificate(
    certificate_id: UUID,
    payload: CertificateReissueRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    row = (
        await db.execute(
            select(Certificate, Enrollment, Student, User, Class, Course)
            .join(Enrollment, Certificate.enrollment_id == Enrollment.id)
            .join(Student, Enrollment.student_id == Student.id)
            .join(User, Student.user_id == User.id)
            .join(Class, Enrollment.class_id == Class.id)
            .join(Course, Class.course_id == Course.id)
            .where(
                Certificate.id == certificate_id,
                Certificate.tenant_id == tenant_id,
                Enrollment.tenant_id == tenant_id,
                Student.tenant_id == tenant_id,
                Class.tenant_id == tenant_id,
                Course.tenant_id == tenant_id,
            )
            .with_for_update(of=Certificate)
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Certificate not found")
    old, enrollment, _student, _user, _class, course = row

    profile = (
        await db.execute(
            select(CourseComplianceProfile).where(
                CourseComplianceProfile.tenant_id == tenant_id,
                CourseComplianceProfile.course_id == course.id,
            )
        )
    ).scalar_one_or_none()
    if profile is None:
        return await legacy_certificates.reissue_certificate(
            certificate_id=certificate_id,
            payload=payload,
            db=db,
            current_user=current_user,
        )

    if enrollment.status != EnrollmentStatus.CONCLUIDA:
        raise HTTPException(status_code=409, detail="Enrollment is not completed")
    if old.status == "SUPERSEDED":
        raise HTTPException(status_code=409, detail="Certificate was already superseded")
    if old.status == "PENDING_SIGNATURE":
        raise HTTPException(
            status_code=409,
            detail="Pending-signature certificate must be revoked before a new reissue",
        )

    live_replacement = (
        await db.execute(
            select(Certificate.id).where(
                Certificate.tenant_id == tenant_id,
                Certificate.enrollment_id == enrollment.id,
                Certificate.id != old.id,
                Certificate.status.in_(["ACTIVE", "PENDING_SIGNATURE"]),
            )
        )
    ).scalar_one_or_none()
    if live_replacement:
        raise HTTPException(
            status_code=409,
            detail="A live replacement certificate already exists for this enrollment",
        )

    reason = payload.reason.strip()
    if old.status == "ACTIVE":
        old.status = "SUPERSEDED"
        old.revoked_at = utc_now()
        old.revoked_by = UUID(current_user["user_id"])
        old.revocation_reason = f"Superseded: {reason}"
        db.add(
            CertificateEvent(
                tenant_id=tenant_id,
                certificate_id=old.id,
                event_type="SUPERSEDED",
                actor_id=old.revoked_by,
                reason=reason,
            )
        )
        await db.flush()

    try:
        prepared = await CertificateDocumentService.prepare_document(
            db,
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            actor_id=UUID(current_user["user_id"]),
            supersedes_id=old.id,
            reason=reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return prepared.certificate
