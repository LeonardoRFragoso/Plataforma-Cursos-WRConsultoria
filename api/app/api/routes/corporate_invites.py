from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.normalization import validate_cnpj
from app.core.security import get_current_admin, get_current_tenant_id
from app.core.utils import utc_now
from app.models.company import Company
from app.models.corporate import (
    CorporateEmployeeLinkEvent,
    CorporateInvite,
    CorporateTrainingRequest,
)
from app.models.one_time_token import OneTimeToken
from app.models.student import Student
from app.models.user import User
from app.schemas.corporate import (
    CorporateInviteResponse,
    CorporateLinkEventAnnotation,
    CorporateLinkEventResponse,
    CorporateRequestConvert,
    CorporateRequestConvertResponse,
)

router = APIRouter()


async def _sync_invite_status(db: AsyncSession, invite: CorporateInvite) -> None:
    if invite.status != "PENDING" or not invite.student_id:
        return
    user = (
        await db.execute(
            select(User)
            .join(Student, Student.user_id == User.id)
            .where(Student.id == invite.student_id, Student.tenant_id == invite.tenant_id)
        )
    ).scalar_one_or_none()
    if user and user.is_active:
        invite.status = "ACCEPTED"
        invite.accepted_at = invite.accepted_at or utc_now()
    elif invite.expires_at and invite.expires_at <= utc_now():
        invite.status = "EXPIRED"


def _response(invite: CorporateInvite) -> CorporateInviteResponse:
    return CorporateInviteResponse(
        id=invite.id,
        company_id=invite.company_id,
        student_id=invite.student_id,
        email=invite.email,
        full_name=invite.full_name,
        status=invite.status,
        expires_at=invite.expires_at,
        created_at=invite.created_at,
        activation_token=None,
        activation_email_sent=False,
    )


@router.post(
    "/requests/{request_id}/convert",
    response_model=CorporateRequestConvertResponse,
)
async def convert_training_request_to_company(
    request_id: UUID,
    payload: CorporateRequestConvert,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Convert a qualified B2B request into the canonical Company record."""
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
    if not lead.cnpj:
        raise HTTPException(
            status_code=409,
            detail="Informe um CNPJ válido antes de converter a solicitação em empresa.",
        )

    try:
        normalized_cnpj = validate_cnpj(lead.cnpj)
    except ValueError:
        raise HTTPException(status_code=400, detail="CNPJ inválido") from None

    company = (
        await db.execute(
            select(Company).where(
                Company.tenant_id == tenant_id,
                Company.cnpj == normalized_cnpj,
            )
        )
    ).scalar_one_or_none()
    created = False
    if company is None:
        company = Company(
            tenant_id=tenant_id,
            legal_name=lead.company_name.strip(),
            trade_name=payload.trade_name,
            cnpj=normalized_cnpj,
            rh_name=lead.contact_name,
            rh_email=lead.contact_email,
            rh_phone=lead.contact_phone,
            billing_email=str(payload.billing_email) if payload.billing_email else lead.contact_email,
            contract_reference=payload.contract_reference,
            status="ACTIVE",
            notes=payload.notes or lead.admin_notes or lead.message,
        )
        db.add(company)
        await db.flush()
        created = True

    lead.cnpj = normalized_cnpj
    lead.status = "WON"
    if payload.notes:
        lead.admin_notes = payload.notes
    await db.commit()
    await db.refresh(company)

    return CorporateRequestConvertResponse(
        request_id=lead.id,
        company_id=company.id,
        created=created,
        status=lead.status,
    )


@router.get(
    "/companies/{company_id}/link-events",
    response_model=list[CorporateLinkEventResponse],
)
async def list_company_link_events(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    events = (
        await db.execute(
            select(CorporateEmployeeLinkEvent)
            .where(
                CorporateEmployeeLinkEvent.tenant_id == tenant_id,
                or_(
                    CorporateEmployeeLinkEvent.company_id == company_id,
                    CorporateEmployeeLinkEvent.previous_company_id == company_id,
                ),
            )
            .order_by(CorporateEmployeeLinkEvent.created_at.desc())
        )
    ).scalars().all()
    return events


@router.patch(
    "/companies/{company_id}/employees/{student_id}/link-events/latest",
    response_model=CorporateLinkEventResponse,
)
async def annotate_latest_company_link_event(
    company_id: UUID,
    student_id: UUID,
    payload: CorporateLinkEventAnnotation,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Attach the operational reason/actor to the latest membership change.

    PostgreSQL production deployments generate the event with a DB trigger.
    Test/create_all environments do not install triggers, so this endpoint
    also creates the missing UNLINKED audit record after an offboarding call.
    """
    tenant_id = get_current_tenant_id()
    event = (
        await db.execute(
            select(CorporateEmployeeLinkEvent)
            .where(
                CorporateEmployeeLinkEvent.tenant_id == tenant_id,
                CorporateEmployeeLinkEvent.student_id == student_id,
                or_(
                    CorporateEmployeeLinkEvent.company_id == company_id,
                    CorporateEmployeeLinkEvent.previous_company_id == company_id,
                ),
            )
            .order_by(CorporateEmployeeLinkEvent.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if event is None:
        student = (
            await db.execute(
                select(Student).where(
                    Student.id == student_id,
                    Student.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        event = CorporateEmployeeLinkEvent(
            tenant_id=tenant_id,
            student_id=student_id,
            previous_company_id=company_id,
            company_id=student.company_id,
            action="UNLINKED" if student.company_id is None else "TRANSFERRED",
        )
        db.add(event)

    event.reason = payload.reason.strip()
    event.actor_user_id = UUID(current_user["user_id"])
    await db.commit()
    await db.refresh(event)
    return event


@router.get("/companies/{company_id}/invites", response_model=list[CorporateInviteResponse])
async def list_company_invites(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    invites = (
        await db.execute(
            select(CorporateInvite)
            .where(
                CorporateInvite.tenant_id == tenant_id,
                CorporateInvite.company_id == company_id,
            )
            .order_by(CorporateInvite.created_at.desc())
        )
    ).scalars().all()
    for invite in invites:
        await _sync_invite_status(db, invite)
    await db.commit()
    return [_response(invite) for invite in invites]


@router.post("/companies/{company_id}/invites/{invite_id}/revoke", response_model=CorporateInviteResponse)
async def revoke_company_invite(
    company_id: UUID,
    invite_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    invite = (
        await db.execute(
            select(CorporateInvite).where(
                CorporateInvite.id == invite_id,
                CorporateInvite.company_id == company_id,
                CorporateInvite.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="Corporate invite not found")
    await _sync_invite_status(db, invite)
    if invite.status == "ACCEPTED":
        raise HTTPException(status_code=409, detail="Accepted invite cannot be revoked")
    if invite.status == "REVOKED":
        return _response(invite)

    invite.status = "REVOKED"
    invite.revoked_at = utc_now()
    if invite.token_id:
        token = (
            await db.execute(select(OneTimeToken).where(OneTimeToken.id == invite.token_id))
        ).scalar_one_or_none()
        if token and not token.used:
            token.used = True
            token.used_at = utc_now()
    await db.commit()
    await db.refresh(invite)
    return _response(invite)
