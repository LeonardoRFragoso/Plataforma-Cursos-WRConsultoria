from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CertificateCreate(BaseModel):
    enrollment_id: UUID


class CertificateResponse(BaseModel):
    id: UUID
    enrollment_id: UUID
    certificate_number: str
    validation_code: str
    issued_at: datetime
    expires_at: datetime | None = None
    status: str = "ACTIVE"
    version: int = 1
    supersedes_id: UUID | None = None
    revoked_at: datetime | None = None
    revoked_by: UUID | None = None
    revocation_reason: str | None = None
    content_hash: str | None = None
    pdf_path: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StudentCertificateResponse(BaseModel):
    id: UUID
    enrollment_id: UUID
    certificate_number: str
    validation_code: str
    issued_at: datetime
    expires_at: datetime | None = None
    status: str = "ACTIVE"
    version: int = 1
    revocation_reason: str | None = None
    course_id: UUID
    course_name: str
    course_code: str | None = None
    course_category: str | None = None
    cover_image_url: str | None = None
    cover_image_alt: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CertificateValidationRequest(BaseModel):
    validation_code: str


# --- Public validation response (enriched, privacy-safe) ---


class CertificateSummary(BaseModel):
    """Public certificate metadata. No internal UUIDs are exposed."""

    number: str
    validation_code: str
    version: int
    issued_at: datetime
    expires_at: datetime | None = None
    content_hash: str | None = None


class StudentSummary(BaseModel):
    """Public student info — only the full name is exposed for holder
    verification. No CPF, email, phone, address or IDs."""

    name: str


class CourseSummary(BaseModel):
    code: str | None = None
    name: str
    category: str | None = None
    workload_hours: int | None = None
    modality: str | None = None


class JourneyStep(BaseModel):
    """One step in the academic timeline that led to the certificate.

    ``type`` is one of: ENROLLED, COURSE_STARTED, LESSON_COMPLETED,
    COURSE_COMPLETED, CERTIFICATE_ISSUED, CERTIFICATE_REISSUED,
    CERTIFICATE_REVOKED.
    """

    type: str
    label: str
    description: str | None = None
    occurred_at: datetime | None = None
    status: str = "DONE"
    order: int


class JourneyProgress(BaseModel):
    """Aggregate lesson progress shown alongside the timeline."""

    required_lessons_total: int = 0
    required_lessons_completed: int = 0
    completion_percent: float = 0.0


class CertificateJourney(BaseModel):
    progress: JourneyProgress
    steps: list[JourneyStep]
    lessons: list[JourneyStep] = Field(
        default_factory=list,
        description="Per-lesson steps, shown on demand (expandable).",
    )


class CertificateValidationResponse(BaseModel):
    valid: bool
    status: str | None = None
    is_demo: bool = False

    # Nested, privacy-safe payloads.
    certificate: CertificateSummary | None = None
    student: StudentSummary | None = None
    course: CourseSummary | None = None
    journey: CertificateJourney | None = None

    # Backwards-compatible flat fields (kept so existing consumers do not
    # break). New consumers should prefer the nested objects.
    certificate_number: str | None = None
    validation_code: str | None = None
    version: int | None = None
    student_name: str | None = None
    course_name: str | None = None
    issued_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revocation_reason: str | None = None
    content_hash: str | None = None


class CertificateRevokeRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=2000)


class CertificateReissueRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=2000)


class CertificateEventResponse(BaseModel):
    id: UUID
    certificate_id: UUID
    event_type: str
    actor_id: UUID | None = None
    reason: str | None = None
    details: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
