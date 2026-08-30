from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes import compliance as legacy_compliance
from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id
from app.core.utils import utc_now
from app.models.compliance import ComplianceStatus, ProfessionalBlocker
from app.models.professional_evidence import (
    ProfessionalEvidenceStatus,
    ProfessionalEvidenceType,
    TrainingProfessionalEvidence,
)
from app.schemas.compliance import ComplianceProfileResponse, ComplianceReadinessResponse
from app.services.regulatory_rule_registry import NR1_CERTIFICATE_REQUIRED_FIELDS

router = APIRouter(include_in_schema=False)


async def _verified_evidence_types(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    professional_id: UUID,
) -> set[str]:
    now = utc_now()
    values = (
        await db.execute(
            select(TrainingProfessionalEvidence.evidence_type).where(
                TrainingProfessionalEvidence.tenant_id == tenant_id,
                TrainingProfessionalEvidence.professional_id == professional_id,
                TrainingProfessionalEvidence.status == ProfessionalEvidenceStatus.VERIFIED,
                or_(
                    TrainingProfessionalEvidence.expires_at.is_(None),
                    TrainingProfessionalEvidence.expires_at > now,
                ),
            )
        )
    ).scalars().all()
    return {str(item).upper() for item in values}


def _without(blockers: list[str], *values: str) -> list[str]:
    remove = set(values)
    return [item for item in blockers if item not in remove]


async def corrected_readiness_blockers(db, tenant_id, course, profile) -> list[str]:
    """Extend the legacy gate with evidence that can actually resolve blockers.

    The previous NR-10/NR-12 checks were intentionally fail-closed but had no
    evidence model capable of moving them to ready. This layer keeps the
    fail-closed behavior while making every professional blocker resolvable by
    verified, tenant-scoped evidence.
    """
    blockers = list(
        await legacy_compliance._readiness_blockers(db, tenant_id, course, profile)
    )

    configured_fields = {
        str(item).strip().lower()
        for item in (profile.certificate_required_fields or [])
        if str(item).strip()
    }
    missing_nr1_fields = [
        item for item in NR1_CERTIFICATE_REQUIRED_FIELDS if item not in configured_fields
    ]
    if missing_nr1_fields:
        blockers.append(
            "NR1_REQUIRED_CERTIFICATE_FIELDS_MISSING: " + ", ".join(missing_nr1_fields)
        )

    professional_id = profile.technical_responsible_id
    if professional_id:
        evidence = await _verified_evidence_types(
            db,
            tenant_id=tenant_id,
            professional_id=professional_id,
        )
        nr_code = course.code.upper()

        # A populated registration number is a business fact; VERIFIED
        # PROFESSIONAL_REGISTRATION evidence is the audit fact that allows the
        # platform to treat that registration as checked.
        if ProfessionalEvidenceType.PROFESSIONAL_REGISTRATION in evidence:
            blockers = _without(
                blockers,
                ProfessionalBlocker.TECHNICAL_RESPONSIBLE_PENDING_VERIFICATION,
            )
        elif getattr(profile, "technical_responsible_id", None):
            blockers.append(ProfessionalBlocker.TECHNICAL_RESPONSIBLE_PENDING_VERIFICATION)

        if nr_code.startswith("NR-10"):
            if ProfessionalEvidenceType.LEGAL_QUALIFICATION in evidence:
                blockers = _without(
                    blockers,
                    ProfessionalBlocker.ELECTRICAL_LEGAL_QUALIFICATION_REQUIRED,
                )
            else:
                blockers.append(ProfessionalBlocker.ELECTRICAL_LEGAL_QUALIFICATION_REQUIRED)

            if ProfessionalEvidenceType.PROFICIENCY in evidence:
                blockers = _without(
                    blockers,
                    ProfessionalBlocker.PROFICIENCY_EVIDENCE_MISSING,
                )
            else:
                blockers.append(ProfessionalBlocker.PROFICIENCY_EVIDENCE_MISSING)

        if nr_code.startswith("NR-12"):
            if ProfessionalEvidenceType.LEGAL_QUALIFICATION in evidence:
                blockers = _without(
                    blockers,
                    ProfessionalBlocker.LEGAL_QUALIFIED_PROFESSIONAL_REQUIRED,
                )
            else:
                blockers.append(ProfessionalBlocker.LEGAL_QUALIFIED_PROFESSIONAL_REQUIRED)

    # Preserve deterministic ordering while de-duplicating overlapping legacy
    # and evidence-driven blocker paths.
    return list(dict.fromkeys(blockers))


@router.get(
    "/courses/{course_id}/readiness",
    response_model=ComplianceReadinessResponse,
)
async def guarded_compliance_readiness(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    course = await legacy_compliance._load_course(db, tenant_id, course_id)
    profile = await legacy_compliance._load_profile(db, tenant_id, course_id)
    blockers = await corrected_readiness_blockers(db, tenant_id, course, profile)
    return ComplianceReadinessResponse(
        ready=not blockers and profile.status == ComplianceStatus.COMPLIANCE_READY,
        status=profile.status,
        blockers=blockers,
        profile=ComplianceProfileResponse.model_validate(profile),
    )


@router.post(
    "/courses/{course_id}/mark-ready",
    response_model=ComplianceReadinessResponse,
)
async def guarded_mark_compliance_ready(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    course = await legacy_compliance._load_course(
        db,
        tenant_id,
        course_id,
        for_update=True,
    )
    profile = await legacy_compliance._load_profile(db, tenant_id, course_id)
    blockers = await corrected_readiness_blockers(db, tenant_id, course, profile)
    if blockers:
        profile.status = ComplianceStatus.REVIEW_REQUIRED
        await db.commit()
        raise HTTPException(
            status_code=409,
            detail={"message": "Course is not compliance-ready", "blockers": blockers},
        )
    profile.status = ComplianceStatus.COMPLIANCE_READY
    profile.last_compliance_review_at = utc_now()
    await db.commit()
    await db.refresh(profile)
    return ComplianceReadinessResponse(
        ready=True,
        status=profile.status,
        blockers=[],
        profile=ComplianceProfileResponse.model_validate(profile),
    )


@router.post(
    "/courses/{course_id}/apply-official-baseline",
    response_model=ComplianceProfileResponse,
)
async def apply_official_certificate_baseline(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    """Merge source-backed NR-01 certificate fields without inventing facts."""
    tenant_id = get_current_tenant_id()
    await legacy_compliance._load_course(db, tenant_id, course_id, for_update=True)
    profile = await legacy_compliance._load_profile(db, tenant_id, course_id)
    fields = list(profile.certificate_required_fields or [])
    normalized = {str(item).strip().lower() for item in fields}
    for required in NR1_CERTIFICATE_REQUIRED_FIELDS:
        if required not in normalized:
            fields.append(required)
            normalized.add(required)
    profile.certificate_required_fields = fields
    if profile.status == ComplianceStatus.COMPLIANCE_READY:
        profile.status = ComplianceStatus.REVIEW_REQUIRED
    await db.commit()
    await db.refresh(profile)
    return ComplianceProfileResponse.model_validate(profile)
