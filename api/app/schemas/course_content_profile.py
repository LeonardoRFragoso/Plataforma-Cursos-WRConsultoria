"""Pydantic schemas for CourseContentProfile."""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CourseContentProfileBase(BaseModel):
    short_description: str | None = None
    full_description: str | None = None
    target_audience: str | None = None
    general_objective: str | None = None
    specific_objectives: list[str] | None = None
    prerequisites: str | None = None
    learning_outcomes: list[str] | None = None
    syllabus: list[str] | None = None
    modules: list[str] | None = None
    key_topics: list[str] | None = None
    risks_covered: list[str] | None = None
    prevention_topics: list[str] | None = None
    ppe_topics: list[str] | None = None
    emergency_topics: list[str] | None = None
    standards_referenced: list[str] | None = None
    assessment_summary: str | None = None
    recycling_summary: str | None = None
    validity_summary: str | None = None
    technical_responsible: str | None = None
    instructor_information: list[str] | None = None
    review_status: str | None = None
    review_required_fields: list[str] | None = None


class CourseContentProfileCreate(CourseContentProfileBase):
    course_id: UUID


class CourseContentProfileUpdate(CourseContentProfileBase):
    pass


class CourseContentProfileResponse(CourseContentProfileBase):
    id: UUID
    course_id: UUID
    source_manifest: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
