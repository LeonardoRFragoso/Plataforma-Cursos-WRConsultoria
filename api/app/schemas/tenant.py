from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.models.tenant import CustomDomainStatus, TenantStatus


class CustomDomainIn(BaseModel):
    custom_domain: str


class CustomDomainOut(BaseModel):
    id: UUID
    name: str
    slug: str
    custom_domain: str | None
    custom_domain_status: CustomDomainStatus = CustomDomainStatus.NONE
    domain_verification_token: str | None = None
    domain_verified_at: datetime | None = None
    domain_verification_error: str | None = None
    status: TenantStatus
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomDomainVerifyOut(CustomDomainOut):
    dns_instructions: dict | None = None


_HEX_RE = r'^#[0-9A-Fa-f]{6}$'


class TenantBrandingUpdate(BaseModel):
    """Campos de branding que um admin de tenant pode atualizar.

    Campos proibidos (tenant_id, slug, status, plan, custom domain,
    settings de segurança) não estão presentes no schema e nunca podem
    ser alterados por este endpoint.
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    logo_url: str | None = Field(default=None, max_length=2000)
    logo_white_url: str | None = Field(default=None, max_length=2000)
    favicon_url: str | None = Field(default=None, max_length=2000)
    primary_color: str | None = Field(default=None, pattern=_HEX_RE)
    secondary_color: str | None = Field(default=None, pattern=_HEX_RE)
    accent_color: str | None = Field(default=None, pattern=_HEX_RE)

    @field_validator("logo_url", "logo_white_url", "favicon_url")
    @classmethod
    def _validate_url_safe(cls, v: str | None) -> str | None:
        if v is None:
            return v
        # Aceita http(s) URLs; rejeita javascript:/data: perigosos.
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class TenantBrandingResponse(BaseModel):
    id: UUID
    name: str
    logo_url: str | None
    logo_white_url: str | None
    favicon_url: str | None
    primary_color: str | None
    secondary_color: str | None
    accent_color: str | None

    model_config = ConfigDict(from_attributes=True)

