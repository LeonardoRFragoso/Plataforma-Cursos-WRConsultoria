from __future__ import annotations

import base64
import binascii
import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_MAX_LOGO_BYTES = 250 * 1024


def _validate_data_image(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    value = value.strip()
    prefixes = ("data:image/png;base64,", "data:image/jpeg;base64,")
    prefix = next((item for item in prefixes if value.startswith(item)), None)
    if prefix is None:
        raise ValueError("Logo must be a PNG/JPEG data URI")
    encoded = value[len(prefix):]
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Logo data URI is not valid base64") from exc
    if not decoded or len(decoded) > _MAX_LOGO_BYTES:
        raise ValueError("Logo must be between 1 byte and 250 KiB")
    if prefix.startswith("data:image/png") and not decoded.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Logo content does not match PNG MIME type")
    if prefix.startswith("data:image/jpeg") and not decoded.startswith(b"\xff\xd8\xff"):
        raise ValueError("Logo content does not match JPEG MIME type")
    return value


class CertificateVisualConfig(BaseModel):
    """Visual-only configuration. Regulatory facts are intentionally absent."""

    model_config = ConfigDict(extra="forbid")

    preset: Literal["CLASSIC", "MODERN", "MINIMAL"] = "CLASSIC"
    primary_color: str = "#047F37"
    secondary_color: str = "#036B2E"
    accent_color: str = "#D1E7DA"
    background_color: str = "#FFFFFF"
    font_family: Literal["HELVETICA", "TIMES", "COURIER"] = "HELVETICA"
    border_style: Literal["NONE", "SIMPLE", "DOUBLE"] = "SIMPLE"
    background_style: Literal["WHITE", "LIGHT_TINT"] = "WHITE"
    logo_position: Literal["LEFT", "CENTER", "RIGHT"] = "CENTER"
    qr_position: Literal["LEFT", "RIGHT"] = "RIGHT"
    show_issuer_logo: bool = True
    show_secondary_logo: bool = False
    show_verification_seal: bool = True
    logo_data_uri: str | None = None
    secondary_logo_data_uri: str | None = None

    @field_validator("primary_color", "secondary_color", "accent_color", "background_color")
    @classmethod
    def validate_color(cls, value: str) -> str:
        value = value.strip().upper()
        if not _HEX_COLOR.fullmatch(value):
            raise ValueError("Color must use #RRGGBB format")
        return value

    @field_validator("logo_data_uri", "secondary_logo_data_uri")
    @classmethod
    def validate_logo(cls, value: str | None) -> str | None:
        return _validate_data_image(value)


class CertificateTemplateCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=96)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        value = value.strip().lower()
        if not _SLUG.fullmatch(value):
            raise ValueError("Slug must contain lowercase letters, digits and hyphens")
        return value


class CertificateTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    is_active: bool | None = None


class CertificateTemplateResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CertificateTemplateVersionCreate(BaseModel):
    visual_config: CertificateVisualConfig | None = None


class CertificateTemplateVersionUpdate(BaseModel):
    visual_config: CertificateVisualConfig


class CertificateTemplateVersionResponse(BaseModel):
    id: UUID
    template_id: UUID
    version: int
    status: str
    visual_config: dict
    published_at: datetime | None = None
    published_by: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CertificateTemplateAssignmentRequest(BaseModel):
    template_id: UUID


class CertificateTemplateAssignmentResponse(BaseModel):
    id: UUID
    course_id: UUID
    template_id: UUID
    assigned_by: UUID | None = None
    assigned_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CertificateStudioPreviewRequest(BaseModel):
    visual_config: CertificateVisualConfig


class CertificateTemplateResolution(BaseModel):
    source: Literal["SYSTEM", "TENANT"]
    template_id: UUID | None = None
    template_version_id: UUID | None = None
    template_name: str
    version: int
    visual_config: CertificateVisualConfig
