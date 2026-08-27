from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AssessmentQuestionResponse(BaseModel):
    id: str
    prompt: str
    options: list[str]


class AssessmentStartResponse(BaseModel):
    attempt_id: UUID
    course_id: UUID
    attempt_number: int
    minimum_score: float
    question_version: str
    questions: list[AssessmentQuestionResponse]
    started_at: datetime


class AssessmentSubmitRequest(BaseModel):
    answers: dict[str, int]


class AssessmentResultResponse(BaseModel):
    attempt_id: UUID
    score: float
    minimum_score: float
    correct_answers: int
    total_questions: int
    passed: bool
    status: str
    completed_at: datetime


class AssessmentStatusResponse(BaseModel):
    required: bool
    lessons_complete: bool
    minimum_score: float = 70.0
    attempts: int = 0
    passed: bool = False
    passed_attempt_id: UUID | None = None
    best_score: float | None = None
    confirmation_required: bool = False
    completion_confirmed: bool = False
    certificate_id: UUID | None = None
    certificate_validation_code: str | None = None
    regulatory_state: str | None = None


class CompletionConfirmationRequest(BaseModel):
    password: str = Field(min_length=1)
    declaration_accepted: bool


class CompletionConfirmationResponse(BaseModel):
    confirmed: bool
    certificate_id: UUID | None = None
    certificate_number: str | None = None
    validation_code: str | None = None
    is_demo: bool = False
    regulatory_state: str | None = None


class DemoEnrollmentResponse(BaseModel):
    enrollment_id: UUID
    course_id: UUID
    status: str
    created: bool
