from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TrainingProfessionalBase(BaseModel):
    full_name: str = Field(min_length=3, max_length=255)
    cpf: str
    qualification: str = Field(min_length=2)
    professional_council: str | None = None
    registration_number: str | None = None
    registration_state: str | None = Field(default=None, max_length=2)
    is_active: bool = True
    signature_method: str | None = None
    signature_reference: str | None = None
    signature_verified_at: datetime | None = None

    @field_validator("cpf")
    @classmethod
    def normalize_cpf(cls, value: str) -> str:
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) != 11:
            raise ValueError("CPF deve conter 11 dígitos")
        return digits


class TrainingProfessionalCreate(TrainingProfessionalBase):
    pass


class TrainingProfessionalResponse(TrainingProfessionalBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime


class PedagogicalProjectCreate(BaseModel):
    general_objective: str
    principles_and_concepts: str
    pedagogical_strategy: str
    support_infrastructure: str
    theoretical_program: list[str] = Field(min_length=1)
    practical_program: list[str] = []
    module_objectives: list[dict] = Field(min_length=1)
    workload_hours: int = Field(gt=0)
    minimum_daily_dedication_minutes: int = Field(gt=0)
    maximum_completion_days: int = Field(gt=0)
    target_audience: str
    didactic_materials: list[str] = Field(min_length=1)
    learning_tools: list[str] = Field(min_length=1)
    assessment_methodology: str
    practical_strategy: str | None = None
    normative_reference: str
    technical_responsible_id: UUID


class PedagogicalProjectResponse(PedagogicalProjectCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    course_id: UUID
    version: int
    status: str
    approved_at: datetime | None = None
    approved_by_user_id: UUID | None = None
    valid_until: date | None = None
    created_at: datetime
    updated_at: datetime


class ProfessionalAssignmentCreate(BaseModel):
    pedagogical_project_version_id: UUID
    professional_id: UUID
    role: str
    is_primary: bool = False


class ComplianceProfileUpsert(BaseModel):
    regulatory_standard: str
    regulatory_version: str
    regulatory_source_url: str
    regulatory_effective_from: date | None = None
    delivery_mode: str
    requires_practical_component: bool = False
    practical_component_description: str | None = None
    requires_final_assessment: bool = True
    minimum_score: float = Field(default=60.0, ge=0, le=100)
    validity_period_months: int | None = Field(default=None, gt=0)
    recycling_rule: str | None = None
    regulatory_prerequisites: str | None = None
    certificate_required_fields: list[str] = []
    practical_scenario_question_count: int = Field(default=1, ge=0)
    access_log_retention_months_after_validity: int = Field(default=24, ge=24)
    pedagogical_project_version_id: UUID | None = None
    technical_responsible_id: UUID | None = None
    review_notes: str | None = None


class ComplianceProfileResponse(ComplianceProfileUpsert):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    course_id: UUID
    status: str
    last_compliance_review_at: datetime | None = None
    next_compliance_review_at: datetime | None = None
    approved_at: datetime | None = None
    approved_by_professional_id: UUID | None = None
    official_issuance_enabled: bool
    created_at: datetime
    updated_at: datetime


class ComplianceReadinessResponse(BaseModel):
    ready: bool
    issues: list[str]


class ComplianceApproveRequest(BaseModel):
    approving_professional_id: UUID


class PracticalEvidenceCreate(BaseModel):
    enrollment_id: UUID
    professional_id: UUID
    occurred_on: date
    location: str = Field(min_length=2)
    result: str
    notes: str | None = None


class TrainingAccessLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    student_id: UUID
    enrollment_id: UUID | None
    course_id: UUID
    lesson_id: UUID | None
    event_type: str
    occurred_at: datetime
    retention_until: date | None
