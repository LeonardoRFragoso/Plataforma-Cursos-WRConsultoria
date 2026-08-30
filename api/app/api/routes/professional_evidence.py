from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id
from app.core.utils import utc_now
from app.models.compliance import (
    ComplianceStatus,
    CourseComplianceProfile,
    CourseTrainingProfessional,
    TrainingProfessional,
)
from app.models.professional_evidence import (
    ProfessionalEvidenceStatus,
    TrainingProfessionalEvidence,
)
from app.schemas.professional_evidence import (
    ProfessionalEvidenceCreate,
    ProfessionalEvidenceDecision,
    ProfessionalEvidenceResponse,
)
from app.services.regulatory_rule_registry import (
    NR1_CERTIFICATE_REQUIRED_FIELDS,
    NR1_EAD_CONTROLS,
    official_regulatory_sources,
)

router = APIRouter()


async def _load_professional(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    professional_id: UUID,
) -> TrainingProfessional:
    item = (
        await db.execute(
            select(TrainingProfessional).where(
                TrainingProfessional.id == professional_id,
                TrainingProfessional.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Training professional not found")
    return item


async def _invalidate_affected_profiles(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    professional_id: UUID,
) -> None:
    assignment_course_ids = select(CourseTrainingProfessional.course_id).where(
        CourseTrainingProfessional.tenant_id == tenant_id,
        CourseTrainingProfessional.professional_id == professional_id,
    )
    profiles = (
        await db.execute(
            select(CourseComplianceProfile).where(
                CourseComplianceProfile.tenant_id == tenant_id,
                CourseComplianceProfile.status == ComplianceStatus.COMPLIANCE_READY,
                or_(
                    CourseComplianceProfile.technical_responsible_id == professional_id,
                    CourseComplianceProfile.course_id.in_(assignment_course_ids),
                ),
            )
        )
    ).scalars().all()
    for profile in profiles:
        profile.status = ComplianceStatus.REVIEW_REQUIRED


@router.get("/regulatory-sources")
async def regulatory_sources(
    _current_user: dict = Depends(get_current_admin),
):
    """Expose the public source-backed baseline used by readiness checks."""
    return {
        "sources": official_regulatory_sources(),
        "nr1_certificate_required_fields": list(NR1_CERTIFICATE_REQUIRED_FIELDS),
        "nr1_ead_controls": list(NR1_EAD_CONTROLS),
        "retention_rule": "EAD access logs: retain through course validity end + 2 calendar years",
        "legal_review_notice": (
            "These controls are a software baseline derived from official public sources; "
            "they do not replace validation of WR-specific facts or professional evidence."
        ),
    }


@router.post(
    "/professionals/{professional_id}/evidence",
    response_model=ProfessionalEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_professional_evidence(
    professional_id: UUID,
    payload: ProfessionalEvidenceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _load_professional(db, tenant_id=tenant_id, professional_id=professional_id)
    if payload.expires_at and payload.issued_at and payload.expires_at <= payload.issued_at:
        raise HTTPException(status_code=422, detail="expires_at must be after issued_at")

    item = TrainingProfessionalEvidence(
        tenant_id=tenant_id,
        professional_id=professional_id,
        status=ProfessionalEvidenceStatus.PENDING,
        **payload.model_dump(),
    )
    db.add(item)
    await _invalidate_affected_profiles(
        db,
        tenant_id=tenant_id,
        professional_id=professional_id,
    )
    await db.commit()
    await db.refresh(item)
    return item


@router.get(
    "/professionals/{professional_id}/evidence",
    response_model=list[ProfessionalEvidenceResponse],
)
async def list_professional_evidence(
    professional_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _load_professional(db, tenant_id=tenant_id, professional_id=professional_id)
    return list(
        (
            await db.execute(
                select(TrainingProfessionalEvidence)
                .where(
                    TrainingProfessionalEvidence.tenant_id == tenant_id,
                    TrainingProfessionalEvidence.professional_id == professional_id,
                )
                .order_by(TrainingProfessionalEvidence.created_at.desc())
            )
        ).scalars().all()
    )


@router.post(
    "/professionals/{professional_id}/evidence/{evidence_id}/decision",
    response_model=ProfessionalEvidenceResponse,
)
async def decide_professional_evidence(
    professional_id: UUID,
    evidence_id: UUID,
    payload: ProfessionalEvidenceDecision,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _load_professional(db, tenant_id=tenant_id, professional_id=professional_id)
    item = (
        await db.execute(
            select(TrainingProfessionalEvidence)
            .where(
                TrainingProfessionalEvidence.id == evidence_id,
                TrainingProfessionalEvidence.tenant_id == tenant_id,
                TrainingProfessionalEvidence.professional_id == professional_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Professional evidence not found")

    if payload.status == ProfessionalEvidenceStatus.VERIFIED:
        if not any(
            [
                item.document_reference,
                item.document_sha256,
                item.reference_number,
                item.issuer,
            ]
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Verified evidence requires a document/reference/issuer trace; "
                    "free-text notes alone are not sufficient"
                ),
            )
        if item.expires_at and item.expires_at <= utc_now():
            raise HTTPException(status_code=409, detail="Expired evidence cannot be verified")
        item.verified_at = utc_now()
        item.verified_by = UUID(current_user["user_id"])
    else:
        item.verified_at = None
        item.verified_by = UUID(current_user["user_id"])
    item.status = payload.status
    if payload.notes is not None:
        item.notes = payload.notes.strip() or None
    item.updated_at = utc_now()

    await _invalidate_affected_profiles(
        db,
        tenant_id=tenant_id,
        professional_id=professional_id,
    )
    await db.commit()
    await db.refresh(item)
    return item
