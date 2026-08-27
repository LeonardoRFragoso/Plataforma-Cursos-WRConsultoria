from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id, get_current_user
from app.models.certificate import Certificate, CertificateEvent
from app.models.certificate_document import CertificateDocument, CertificateDocumentStatus
from app.models.enrollment import Enrollment
from app.models.student import Student
from app.models.user import User
from app.schemas.certificate_document import (
    CertificateDocumentIntegrityResponse,
    CertificateDocumentPrepareResponse,
    CertificateDocumentResponse,
    CertificateDocumentSnapshotResponse,
)
from app.services.certificate_studio_service import (
    StudioCertificateDocumentService as CertificateDocumentService,
)

router = APIRouter()


async def _document_context(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    certificate_id: UUID,
):
    row = (
        await db.execute(
            select(CertificateDocument, Certificate, Enrollment, Student, User)
            .join(Certificate, CertificateDocument.certificate_id == Certificate.id)
            .join(Enrollment, CertificateDocument.enrollment_id == Enrollment.id)
            .join(Student, Enrollment.student_id == Student.id)
            .join(User, Student.user_id == User.id)
            .where(
                CertificateDocument.tenant_id == tenant_id,
                CertificateDocument.certificate_id == certificate_id,
                Certificate.tenant_id == tenant_id,
                Enrollment.tenant_id == tenant_id,
                Student.tenant_id == tenant_id,
                User.tenant_id == tenant_id,
            )
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Certificate document not found")
    return row


def _authorize_owner_or_admin(user: User, current_user: dict) -> None:
    if current_user.get("role") in {"admin", "super_admin"}:
        return
    if current_user.get("role") == "student" and str(user.id) == current_user.get("user_id"):
        return
    raise HTTPException(status_code=403, detail="Cannot access this certificate document")


@router.post(
    "/enrollments/{enrollment_id}/prepare",
    response_model=CertificateDocumentPrepareResponse,
    status_code=status.HTTP_201_CREATED,
)
async def prepare_certificate_document(
    enrollment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Freeze the regulatory snapshot, visual template and exact pre-signature PDF."""
    tenant_id = get_current_tenant_id()
    try:
        prepared = await CertificateDocumentService.prepare_document(
            db,
            tenant_id=tenant_id,
            enrollment_id=enrollment_id,
            actor_id=UUID(current_user["user_id"]),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return CertificateDocumentPrepareResponse(
        certificate_id=prepared.certificate.id,
        certificate_number=prepared.certificate.certificate_number,
        validation_code=prepared.certificate.validation_code,
        certificate_status=prepared.certificate.status,
        document=CertificateDocumentResponse.model_validate(prepared.document),
        created=prepared.created,
    )


@router.get(
    "/{certificate_id}",
    response_model=CertificateDocumentResponse,
)
async def get_certificate_document(
    certificate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    document, _certificate, _enrollment, _student, user = await _document_context(
        db,
        tenant_id=tenant_id,
        certificate_id=certificate_id,
    )
    _authorize_owner_or_admin(user, current_user)
    return document


@router.get(
    "/{certificate_id}/snapshot",
    response_model=CertificateDocumentSnapshotResponse,
)
async def get_certificate_document_snapshot(
    certificate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    document, _certificate, _enrollment, _student, _user = await _document_context(
        db,
        tenant_id=tenant_id,
        certificate_id=certificate_id,
    )
    return CertificateDocumentSnapshotResponse(
        certificate_id=certificate_id,
        snapshot_version=document.snapshot_version,
        snapshot_sha256=document.snapshot_sha256,
        snapshot=document.snapshot,
    )


@router.post(
    "/{certificate_id}/verify-integrity",
    response_model=CertificateDocumentIntegrityResponse,
)
async def verify_certificate_document_integrity(
    certificate_id: UUID,
    original: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    document, certificate, _enrollment, _student, _user = await _document_context(
        db,
        tenant_id=tenant_id,
        certificate_id=certificate_id,
    )
    try:
        result = await CertificateDocumentService.verify_integrity(
            document=document,
            original=original,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Certificate artifact not found") from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    db.add(
        CertificateEvent(
            tenant_id=tenant_id,
            certificate_id=certificate.id,
            event_type=("INTEGRITY_VERIFIED" if result.valid else "INTEGRITY_FAILED"),
            actor_id=UUID(current_user["user_id"]),
            details=(
                f"artifact={result.artifact};expected={result.expected_sha256};"
                f"actual={result.actual_sha256};size={result.size_bytes}"
            ),
        )
    )
    await db.commit()
    return CertificateDocumentIntegrityResponse(
        certificate_id=certificate.id,
        document_status=document.status,
        artifact=result.artifact,
        valid=result.valid,
        expected_sha256=result.expected_sha256,
        actual_sha256=result.actual_sha256,
        size_bytes=result.size_bytes,
        checked_at=result.checked_at,
    )


async def _download(
    *,
    certificate_id: UUID,
    original: bool,
    db: AsyncSession,
    current_user: dict,
) -> Response:
    tenant_id = get_current_tenant_id()
    document, certificate, _enrollment, _student, user = await _document_context(
        db,
        tenant_id=tenant_id,
        certificate_id=certificate_id,
    )
    _authorize_owner_or_admin(user, current_user)

    if original and current_user.get("role") not in {"admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Original pre-signature artifact is admin-only")
    if (
        not original
        and document.status != CertificateDocumentStatus.SIGNED
        and current_user.get("role") == "student"
    ):
        raise HTTPException(
            status_code=409,
            detail="Certificate document is still pending digital signature",
        )

    try:
        integrity = await CertificateDocumentService.verify_integrity(
            document=document,
            original=original,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Certificate artifact not found") from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not integrity.valid:
        db.add(
            CertificateEvent(
                tenant_id=tenant_id,
                certificate_id=certificate.id,
                event_type="INTEGRITY_FAILED",
                actor_id=UUID(current_user["user_id"]),
                details=(
                    f"artifact={integrity.artifact};expected={integrity.expected_sha256};"
                    f"actual={integrity.actual_sha256}"
                ),
            )
        )
        await db.commit()
        raise HTTPException(
            status_code=409,
            detail="Stored certificate artifact failed SHA-256 integrity verification",
        )

    filename_suffix = "original" if integrity.artifact == "ORIGINAL" else "signed"
    return Response(
        content=integrity.pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f"attachment; filename=certificate-{certificate.certificate_number}-{filename_suffix}.pdf"
            ),
            "X-Certificate-SHA256": integrity.actual_sha256,
            "X-Certificate-Artifact": integrity.artifact,
            "X-Certificate-Document-Status": document.status,
        },
    )


@router.get("/{certificate_id}/download")
async def download_certificate_document(
    certificate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Download the signed bytes; admins may inspect pending originals."""
    return await _download(
        certificate_id=certificate_id,
        original=False,
        db=db,
        current_user=current_user,
    )


@router.get("/{certificate_id}/original")
async def download_original_certificate_document(
    certificate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Download the immutable pre-signature artifact for audit purposes."""
    return await _download(
        certificate_id=certificate_id,
        original=True,
        db=db,
        current_user=current_user,
    )


# Certificate Studio is intentionally mounted under the trusted-document domain.
# It is admin-only and cannot edit regulatory/academic snapshot facts.
from app.api.routes import certificate_studio as _certificate_studio  # noqa: E402

router.include_router(_certificate_studio.router, prefix="/studio")
