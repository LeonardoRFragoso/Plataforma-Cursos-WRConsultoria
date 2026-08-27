from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RetentionPolicyPayload(BaseModel):
    certificate_retention_days: int | None = Field(default=None, gt=0)
    assessment_retention_days: int | None = Field(default=None, gt=0)
    training_event_retention_days: int | None = Field(default=None, gt=0)
    student_confirmation_retention_days: int | None = Field(default=None, gt=0)
    practical_evidence_retention_days: int | None = Field(default=None, gt=0)
    legal_basis: str | None = Field(default=None, max_length=4000)
    purpose: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("legal_basis", "purpose", "notes")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class RetentionPolicyCreate(RetentionPolicyPayload):
    pass


class RetentionPolicyUpdate(RetentionPolicyPayload):
    pass


class RetentionPolicyResponse(RetentionPolicyPayload):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    version: int
    status: str
    approved_at: datetime | None
    approved_by: UUID | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class ComplianceOperationsSummary(BaseModel):
    generated_at: datetime
    course_status_counts: dict[str, int]
    enrollment_state_counts: dict[str, int]
    signing_job_status_counts: dict[str, int]
    reviews_expired: int
    reviews_due_30_days: int
    signer_profile_enabled: bool
    signer_certificate_expires_30_days: bool
    signer_certificate_expired: bool
    signer_certificate_not_after: datetime | None
    enrollments_without_ledger_events: int
    approved_retention_policy_version: int | None
    retention_policy_ready: bool


class ComplianceClassReport(BaseModel):
    generated_at: datetime
    class_id: UUID
    class_status: str
    course_id: UUID
    course_code: str
    course_name: str
    regulatory_standard: str
    regulatory_version: str
    start_date: str
    end_date: str
    pedagogical_project_version_id: UUID | None
    enrollment_count: int
    enrollment_state_counts: dict[str, int]
    training_event_count: int
    certificate_status_counts: dict[str, int]
    signing_job_status_counts: dict[str, int]
