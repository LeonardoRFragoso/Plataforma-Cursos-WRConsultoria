"""B2B read-only academic schemas for Central WR integration.

These schemas are intentionally minimal and LGPD-safe:
- No CPF, no password_hash, no JWT, no email unless necessary
- No write fields
- Aggregated counts for dashboard use
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

# ---- Pagination ----

class B2BPageMeta(BaseModel):
    skip: int
    limit: int
    total: int


class B2BContextResponse(BaseModel):
    """Authenticated B2B client context (no secret).

    Returned by ``GET /api/v1/b2b/context`` so Central WR can verify
    that the LMS tenant binding matches the credential's actual tenant.
    """
    tenant_id: UUID
    tenant_slug: str | None
    client_id: str
    scopes: list[str]


class B2BPageResponse(BaseModel):
    """Generic paginated response for B2B list endpoints."""
    meta: B2BPageMeta
    data: list


# ---- Summary (dashboard) ----

class B2BAcademicSummary(BaseModel):
    """Aggregated academic KPIs for the Central WR dashboard."""
    active_courses: int
    active_classes: int
    active_students: int
    active_enrollments: int
    completed_enrollments: int
    certificates_issued: int
    avg_progress_percent: float
    classes_in_progress: int


# ---- Courses ----

class B2BCourse(BaseModel):
    id: UUID
    code: str
    name: str
    category: str
    carga_horaria: int
    modality: str
    is_active: bool
    classes_count: int
    students_count: int
    created_at: datetime


class B2BCourseDetail(BaseModel):
    id: UUID
    code: str
    name: str
    category: str
    description: str | None
    carga_horaria: int
    modality: str
    tipo_curso: str
    price: float
    is_active: bool
    classes_count: int
    enrollments_count: int
    created_at: datetime


# ---- Classes ----

class B2BClass(BaseModel):
    id: UUID
    course_id: UUID
    course_name: str
    status: str
    start_date: date
    end_date: date
    max_students: int
    location: str | None
    enrollments_count: int
    company_name: str | None


class B2BClassDetail(BaseModel):
    id: UUID
    course_id: UUID
    course_name: str
    status: str
    start_date: date
    end_date: date
    max_students: int
    location: str | None
    description: str | None
    enrollments_count: int
    completed_count: int
    company_name: str | None


# ---- Students ----

class B2BStudent(BaseModel):
    """LGPD-safe student representation for B2B consumers."""
    id: UUID
    full_name: str
    email: str | None
    status: str
    company: str | None
    enrollments_count: int


class B2BStudentDetail(BaseModel):
    id: UUID
    full_name: str
    email: str | None
    company: str | None
    enrollments_count: int
    completed_count: int
    certificates_count: int


# ---- Enrollments ----

class B2BEnrollment(BaseModel):
    id: UUID
    student_id: UUID
    student_name: str
    course_name: str
    class_id: UUID | None
    status: str
    source: str
    enrollment_date: datetime
    progress_percent: float


class B2BEnrollmentDetail(BaseModel):
    id: UUID
    student_id: UUID
    student_name: str
    course_id: UUID
    course_name: str
    class_id: UUID | None
    status: str
    source: str
    enrollment_date: datetime
    lessons_completed: int
    lessons_total: int
    progress_percent: float


# ---- Certificates ----

class B2BCertificate(BaseModel):
    """Read-only certificate for B2B consumers."""
    id: UUID
    student_name: str
    course_name: str
    certificate_number: str
    validation_code: str
    issued_at: datetime
    expires_at: datetime | None
    status: str


# ---- Course progress (aggregated) ----

class B2BCourseProgress(BaseModel):
    course_id: UUID
    course_name: str
    total_enrollments: int
    completed: int
    in_progress: int
    avg_progress_percent: float
