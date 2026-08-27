from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.utils import utc_now
from app.services.assessment_service import MINIMUM_SCORE


class TrainingProfessionalCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    cpf: str
    qualification: str = Field(min_length=2)
    professional_registration: str | None = Field(default=None, max_length=128)
    council: str | None = Field(default=None, max_length=64)
    registration_state: str | None = Field(default=None, max_length=8)


class TrainingProfessionalUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    qualification: str | None = Field(default=None, min_length=2)
    professional_registration: str | None = Field(default=None, max_length=128)
    council: str | None = Field(default=None, max_length=64)
    registration_state: str | None = Field(default=None, max_length=8)
    is_active: bool | None = None


class TrainingProfessionalResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    full_name: str
    cpf: str
    qualification: str
    professional_registration: str | None
    council: str | None
    registration_state: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PedagogicalProjectCreate(BaseModel):
    general_objective: str = Field(min_length=2)
    specific_objectives: list[str] = Field(default_factory=list)
    target_audience: str = Field(min_length=2)
    teaching_strategy: str = Field(min_length=2)
    syllabus: list[str] = Field(default_factory=list)
    workload_hours: float = Field(gt=0)
    delivery_mode: str
    materials: list[str] = Field(default_factory=list)
    assessment_methodology: str = Field(min_length=2)


class PedagogicalProjectUpdate(BaseModel):
    general_objective: str | None = Field(default=None, min_length=2)
    specific_objectives: list[str] | None = None
    target_audience: str | None = Field(default=None, min_length=2)
    teaching_strategy: str | None = Field(default=None, min_length=2)
    syllabus: list[str] | None = None
    workload_hours: float | None = Field(default=None, gt=0)
    delivery_mode: str | None = None
    materials: list[str] | None = None
    assessment_methodology: str | None = Field(default=None, min_length=2)
    status: str | None = None


class PedagogicalProjectApproval(BaseModel):
    approval_notes: str | None = None


class PedagogicalProjectResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    course_id: UUID
    version: int
    status: str
    general_objective: str
    specific_objectives: list[str]
    target_audience: str
    teaching_strategy: str
    syllabus: list[str]
    workload_hours: float
    delivery_mode: str
    materials: list[str]
    assessment_methodology: str
    approval_notes: str | None
    approved_at: datetime | None
    approved_by: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ComplianceProfileUpsert(BaseModel):
    regulatory_standard: str = Field(min_length=1, max_length=64)
    regulatory_version: str = Field(min_length=1, max_length=128)
    delivery_mode: str
    requires_practical_component: bool = False
    requires_final_assessment: bool = True
    minimum_score: float | None = Field(default=None, ge=0, le=100)
    validity_period_months: int | None = Field(default=None, gt=0)
    prerequisites: str | None = None
    certificate_required_fields: list[str] = Field(default_factory=list)
    technical_responsible_id: UUID | None = None
    pedagogical_project_version_id: UUID | None = None
    next_compliance_review_at: datetime | None = None

    @model_validator(mode="after")
    def validate_assessment_policy(self):
        """Keep compliance metadata aligned with the assessment engine in this slice."""
        if self.requires_final_assessment:
            if self.minimum_score is None:
                raise ValueError(
                    "minimum_score is required when final assessment is required"
                )
            if abs(float(self.minimum_score) - float(MINIMUM_SCORE)) >= 0.01:
                raise ValueError(
                    "minimum_score must match the active assessment policy "
                    f"({MINIMUM_SCORE:g})"
                )
        return self


class ComplianceProfileResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    course_id: UUID
    regulatory_standard: str
    regulatory_version: str
    delivery_mode: str
    requires_practical_component: bool
    requires_final_assessment: bool
    minimum_score: float | None
    validity_period_months: int | None
    prerequisites: str | None
    certificate_required_fields: list[str]
    technical_responsible_id: UUID | None
    pedagogical_project_version_id: UUID | None
    last_compliance_review_at: datetime | None
    next_compliance_review_at: datetime | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CourseProfessionalAssignmentCreate(BaseModel):
    professional_id: UUID
    role: str


class CourseProfessionalAssignmentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    course_id: UUID
    professional_id: UUID
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ComplianceReadinessResponse(BaseModel):
    ready: bool
    status: str
    blockers: list[str]
    profile: ComplianceProfileResponse

    @model_validator(mode="after")
    def surface_expired_review(self):
        """Never present an expired review date as currently ready."""
        next_review = self.profile.next_compliance_review_at
        if next_review is not None:
            if next_review.tzinfo is not None:
                next_review = next_review.replace(tzinfo=None)
            if next_review <= utc_now():
                self.ready = False
                blocker = "Compliance review date has expired"
                if blocker not in self.blockers:
                    self.blockers.append(blocker)
        return self
