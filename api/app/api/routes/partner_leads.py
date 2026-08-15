from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_super_admin, get_current_user
from app.core.utils import utc_now
from app.models.tenant import PartnerLead, PartnerLeadStatus, Tenant, TenantStatus
from app.models.user import User, UserRole

router = APIRouter()


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
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    result = await db.execute(select(PartnerLead))
    return result.scalars().all()


@router.post("/{lead_id}/approve")
async def approve_partner_lead(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_super_admin),
):
    result = await db.execute(select(PartnerLead).where(PartnerLead.id == lead_id))
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
        email=lead.contact_email,
        full_name=lead.contact_name,
        role=UserRole.ADMIN,
        tenant_id=tenant.id,
    )
    db.add(admin_user)

    await db.commit()
    return {"tenant_id": tenant.id, "admin_user_id": admin_user.id}
