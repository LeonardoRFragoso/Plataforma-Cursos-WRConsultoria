from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.utils import utc_now


class RegulatoryStateResponse(BaseModel):
    enrollment_id: UUID
    student_id: UUID
    course_id: UUID
    regulatory: bool
    state: str
    blockers: list[str] = Field(default_factory=list)
    last_evaluated_at: datetime


class RegulatoryCompletionConfirmRequest(BaseModel):
    password: str = Field(min_length=1)
    declaration_accepted: bool


class RegulatoryCompletionConfirmResponse(BaseModel):
    confirmed: bool
    state: RegulatoryStateResponse


class PracticalTrainingRecordCreate(BaseModel):
    instructor_id: UUID
    result: str
    performed_at: datetime
    duration_minutes: int | None = Field(default=None, gt=0)
    location: str = Field(min_length=2, max_length=255)
    notes: str | None = Field(default=None, max_length=4000)
    supersedes_id: UUID | None = None

    @field_validator("result")
    @classmethod
    def normalize_result(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"PENDING", "SATISFACTORY", "UNSATISFACTORY"}:
            raise ValueError("result must be PENDING, SATISFACTORY or UNSATISFACTORY")
        return normalized

    @field_validator("performed_at")
    @classmethod
    def reject_future_performance(cls, value: datetime) -> datetime:
        normalized = (
            value.astimezone(UTC).replace(tzinfo=None)
            if value.tzinfo is not None
            else value
        )
        if normalized > utc_now():
            raise ValueError("performed_at cannot be in the future")
        return normalized

    @field_validator("location")
    @classmethod
    def clean_location(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("location cannot be empty")
        return cleaned


class PracticalTrainingRecordResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    enrollment_id: UUID
    student_id: UUID
    course_id: UUID
    instructor_id: UUID
    supersedes_id: UUID | None
    result: str
    performed_at: datetime
    duration_minutes: int | None
    location: str
    notes: str | None
    instructor_snapshot: dict
    recorded_by: UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrainingSessionResponse(BaseModel):
    session_id: UUID
    enrollment_id: UUID
    course_id: UUID
    started_at: datetime


class TrainingSessionEndResponse(BaseModel):
    session_id: UUID
    ended_at: datetime


class TrainingAccessEventResponse(BaseModel):
    id: UUID
    enrollment_id: UUID
    student_id: UUID
    course_id: UUID
    lesson_id: UUID | None
    actor_user_id: UUID | None
    event_type: str
    occurred_at: datetime
    session_id: UUID | None
    client_fingerprint: str | None
    details: dict

    model_config = ConfigDict(from_attributes=True)


class TrainingEvidenceExportResponse(BaseModel):
    enrollment_id: UUID
    state: RegulatoryStateResponse
    practical_records: list[PracticalTrainingRecordResponse]
    events: list[TrainingAccessEventResponse]
    exported_at: datetime
