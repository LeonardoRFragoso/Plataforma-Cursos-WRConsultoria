from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TrainingProfessionalCreate(BaseModel):
    full_name: str = Field(min_length=3, max_length=255)
    cpf: str | None = None
    professional_role: str
    qualification: str = Field(min_length=2)
    professional_council: str | None = None
    registration_number: str | None = None
    proficiency_evidence: str | None = None
    signature_method: str | None = None
    is_active: bool = True


class TrainingProfessionalResponse(TrainingProfessionalCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime


class PedagogicalProjectCreate(BaseModel):
    version: int = Field(default=1, ge=1)
    general_objective: str | None = None
    safety_principles: str | None = None
    pedagogical_strategy: str | None = None
    operational_infrastructure: str | None = None
    theoretical_program: list[Any] = Field(default_factory=list)
    practical_program: list[Any] = Field(default_factory=list)
    module_objectives: list[Any] = Field(default_factory=list)
    workload_hours: float | None = Field(default=None, gt=0)
    minimum_daily_dedication_minutes: int | None = Field(default=None, gt=0)
    maximum_completion_days: int | None = Field(default=None, gt=0)
    target_audience: str | None = None
    teaching_materials: list[Any] = Field(default_factory=list)
    learning_tools: list[Any] = Field(default_factory=list)
    assessment_methodology: str | None = None
    support_channel: str | None = None
    normative_reference: str | None = None


class PedagogicalProjectResponse(PedagogicalProjectCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    course_id: UUID
    status: str
    approved_at: datetime | None = None
    approved_by: UUID | None = None
    valid_until: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ComplianceProfileUpdate(BaseModel):
    regulatory_standard: str | None = None
    regulatory_version: str | None = None
    normative_source_url: str | None = None
    required_delivery_mode: str | None = None
    requires_practical_component: bool | None = None
    practical_minimum_percent: float | None = Field(default=None, ge=0, le=100)
    requires_final_assessment: bool | None = None
    assessment_practical_scenarios_validated: bool | None = None
    minimum_score: float | None = Field(default=None, ge=0, le=100)
    minimum_workload_hours: float | None = Field(default=None, gt=0)
    periodicity_months: int | None = Field(default=None, gt=0)
    prerequisites: str | None = None
    technical_responsible_id: UUID | None = None
    pedagogical_project_version_id: UUID | None = None
    support_channel_verified: bool | None = None
    blocker_reason: str | None = None
    next_review_at: datetime | None = None


class ComplianceProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    course_id: UUID
    regulatory_standard: str | None
    regulatory_version: str | None
    normative_source_url: str | None
    source_checked_at: datetime | None
    required_delivery_mode: str | None
    requires_practical_component: bool
    practical_minimum_percent: float | None
    requires_final_assessment: bool
    assessment_practical_scenarios_validated: bool
    minimum_score: float | None
    minimum_workload_hours: float | None
    periodicity_months: int | None
    prerequisites: str | None
    technical_responsible_id: UUID | None
    pedagogical_project_version_id: UUID | None
    support_channel_verified: bool
    status: str
    blocker_reason: str | None
    reviewed_at: datetime | None
    reviewed_by: UUID | None
    next_review_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ComplianceReadinessItem(BaseModel):
    course_id: UUID
    course_code: str
    course_name: str
    course_modality: str
    profile_status: str
    regulatory_standard: str | None = None
    required_delivery_mode: str | None = None
    official_certificate_eligible: bool
    blockers: list[str] = Field(default_factory=list)


class PracticalTrainingCreate(BaseModel):
    instructor_id: UUID
    occurred_at: datetime
    location: str = Field(min_length=2)
    duration_minutes: int = Field(gt=0)
    practical_percent: float | None = Field(default=None, ge=0, le=100)
    result: str
    notes: str | None = None


class SessionStartResponse(BaseModel):
    session_id: UUID
    started_at: datetime
    active_seconds: int


class SessionHeartbeatResponse(BaseModel):
    session_id: UUID
    active_seconds: int
    credited_seconds: int
    last_heartbeat_at: datetime
