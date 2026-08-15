from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter()


class TenantBrandingOut(BaseModel):
    name: str
    logo_url: str | None
    logo_white_url: str | None
    favicon_url: str | None
    primary_color: str | None
    secondary_color: str | None
    accent_color: str | None


@router.get("/branding", response_model=TenantBrandingOut)
async def get_branding_by_domain(
    slug: str = Query(default="wr"),
    db: AsyncSession = Depends(get_db),
):
    from app.models.tenant import Tenant

    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return TenantBrandingOut(
        name=tenant.name,
        logo_url=tenant.logo_url,
        logo_white_url=tenant.logo_white_url,
        favicon_url=tenant.favicon_url,
        primary_color=tenant.primary_color,
        secondary_color=tenant.secondary_color,
        accent_color=tenant.accent_color,
    )
