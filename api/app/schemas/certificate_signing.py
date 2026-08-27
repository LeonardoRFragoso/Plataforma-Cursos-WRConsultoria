from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


_SENSITIVE_METADATA_TOKENS = (
    "token",
    "secret",
    "password",
    "private_key",
    "privatekey",
    "pfx",
    "pkcs12",
    "credential",
    "api_key",
    "apikey",
)


def _utc_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


class CertificateSigningProfileUpsert(BaseModel):
    provider: str = Field(default="DISABLED", max_length=64)
    enabled: bool = False
    signer_display_name: str = Field(..., min_length=2, max_length=255)
    signer_identifier: str | None = Field(default=None, max_length=128)
    certificate_fingerprint_sha256: str | None = Field(default=None, max_length=64)
    certificate_serial: str | None = Field(default=None, max_length=256)
    certificate_subject: str | None = Field(default=None, max_length=4000)
    certificate_issuer: str | None = Field(default=None, max_length=4000)
    certificate_not_before: datetime | None = None
    certificate_not_after: datetime | None = None
    key_reference: str | None = Field(default=None, max_length=512)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"DISABLED", "MOCK", "EXTERNAL_PADES_GATEWAY"}:
            raise ValueError("Unsupported signing provider")
        return normalized

    @field_validator("certificate_fingerprint_sha256")
    @classmethod
    def validate_fingerprint(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip().lower().replace(":", "")
        if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError("certificate_fingerprint_sha256 must be a SHA-256 hex digest")
        return normalized

    @field_validator("certificate_not_before", "certificate_not_after")
    @classmethod
    def normalize_certificate_timestamp(cls, value: datetime | None) -> datetime | None:
        return _utc_naive(value)

    @field_validator("provider_metadata")
    @classmethod
    def reject_secrets_in_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 50:
            raise ValueError("provider_metadata has too many entries")
        for raw_key in value:
            key = str(raw_key).strip().lower()
            if any(token in key for token in _SENSITIVE_METADATA_TOKENS):
                raise ValueError(
                    "provider_metadata cannot contain credentials, tokens, PFX or private-key material; use TenantSecret"
                )
        return value


class CertificateSigningProfileResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    provider: str
    enabled: bool
    signer_display_name: str
    signer_identifier: str | None = None
    certificate_fingerprint_sha256: str | None = None
    certificate_serial: str | None = None
    certificate_subject: str | None = None
    certificate_issuer: str | None = None
    certificate_not_before: datetime | None = None
    certificate_not_after: datetime | None = None
    key_reference: str | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CertificateSigningJobResponse(BaseModel):
    id: UUID
    document_id: UUID
    certificate_id: UUID
    profile_id: UUID
    provider: str
    status: str
    provider_job_id: str | None = None
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime | None = None
    last_attempt_at: datetime | None = None
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    result_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CertificateSigningEventResponse(BaseModel):
    id: UUID
    job_id: UUID
    event_type: str
    actor_id: UUID | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CertificateSigningWebhookPayload(BaseModel):
    provider_job_id: str = Field(..., min_length=1, max_length=512)
    status: str = Field(..., min_length=1, max_length=64)
    event_id: str | None = Field(default=None, max_length=256)


class SigningQueueSummary(BaseModel):
    queued: int = 0
    waiting_provider: int = 0
    retry_scheduled: int = 0
    failed: int = 0
    signed: int = 0
    expiring_profiles: int = 0
