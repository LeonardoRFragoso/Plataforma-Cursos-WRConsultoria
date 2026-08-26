from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id
from app.core.utils import utc_now
from app.models.corporate import CorporateInvite
from app.models.one_time_token import OneTimeToken
from app.models.student import Student
from app.models.user import User
from app.schemas.corporate import CorporateInviteResponse

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
