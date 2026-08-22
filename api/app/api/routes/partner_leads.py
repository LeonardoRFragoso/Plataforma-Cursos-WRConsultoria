from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db, get_db_privileged
from app.core.normalization import normalize_email
from app.core.security import get_current_super_admin
from app.core.utils import utc_now
from app.models.tenant import PartnerLead, PartnerLeadStatus, Tenant, TenantStatus
from app.models.user import User, UserRole
from app.services.email_service import EmailServiceError, get_email_service
from app.services.one_time_token_service import OneTimeTokenService

router = APIRouter()

# Environments where raw one-time tokens may be returned in responses.
# Only local development and automated test environments.
_LOCAL_TOKEN_RETURN_ENVS = frozenset({"development", "dev", "test", "testing"})


def _current_env() -> str:
    return getattr(settings, "ENVIRONMENT", "").lower()


def _can_return_token() -> bool:
    """Only local dev/test environments may return raw one-time tokens."""
    return _current_env() in _LOCAL_TOKEN_RETURN_ENVS


class PartnerLeadCreate(BaseModel):
    company_name: str
    cnpj: str | None = None
    contact_name: str
    contact_email: EmailStr
    contact_phone: str | None = None
    message: str | None = None


class PartnerLeadResponse(BaseModel):
    id: UUID
    company_name: str
    contact_name: str
    contact_email: str
    status: str

    class Config:
        from_attributes = True


@router.post("", response_model=PartnerLeadResponse, status_code=status.HTTP_201_CREATED)
async def create_partner_lead(
    payload: PartnerLeadCreate,
    db: AsyncSession = Depends(get_db),
):
    lead = PartnerLead(
        company_name=payload.company_name,
        cnpj=payload.cnpj,
        contact_name=payload.contact_name,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        message=payload.message,
        status=PartnerLeadStatus.NEW,
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead


@router.get("", response_model=list[PartnerLeadResponse])
async def list_partner_leads(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_super_admin),
):
    result = await db.execute(select(PartnerLead))
    leads = result.scalars().all()
    return leads


@router.post("/{lead_id}/approve")
async def approve_partner_lead(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db_privileged),
    current_user: dict = Depends(get_current_super_admin),
):
    stmt = select(PartnerLead).where(PartnerLead.id == lead_id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    if lead.status != PartnerLeadStatus.NEW:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lead already processed",
        )

    tenant = Tenant(
        name=lead.company_name,
        slug=lead.cnpj or lead.company_name.lower().replace(" ", "-"),
        status=TenantStatus.ACTIVE,
        contact_name=lead.contact_name,
        contact_email=lead.contact_email,
        contact_phone=lead.contact_phone,
    )
    db.add(tenant)
    await db.flush()

    lead.tenant_id = tenant.id
    lead.status = PartnerLeadStatus.APPROVED
    lead.approved_at = utc_now()
    lead.approved_by = UUID(current_user["user_id"])

    admin_user = User(
        email=normalize_email(lead.contact_email),
        full_name=lead.contact_name,
        role=UserRole.ADMIN,
        tenant_id=tenant.id,
        is_active=False,
    )
    db.add(admin_user)
    await db.flush()

    activation_token, _ = await OneTimeTokenService.create(
        db, str(admin_user.id), "activation"
    )

    await db.commit()

    # Send activation email (mock mode in dev/test/CI — no real email sent)
    activation_email_sent = False
    try:
        email_service = get_email_service()
        await email_service.send_account_activation(
            to=admin_user.email,
            activation_token=activation_token,
            frontend_url=settings.FRONTEND_URL,
            tenant_name=tenant.name,
        )
        activation_email_sent = True
    except EmailServiceError:
        pass  # Don't fail the signup if email fails

    # In production/staging: NEVER expose raw activation token.
    # In dev/test: return raw token for automated tests.
    returned_token = activation_token if _can_return_token() else None

    return {
        "tenant_id": tenant.id,
        "admin_user_id": admin_user.id,
        "activation_token": returned_token,
        "activation_email_sent": activation_email_sent,
    }
