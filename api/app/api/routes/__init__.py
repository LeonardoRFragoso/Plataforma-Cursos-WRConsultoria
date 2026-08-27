from app.api.routes import (
    assessments,
    auth,
    certificates,
    classes,
    companies,
    courses,
    enrollments,
    lessons,
    payments,
    students,
)

# Import after both source routers are loaded. The module prepends guarded
# student handlers for watch/progress so lesson order cannot be bypassed by
# direct API calls.
from app.api.routes import lesson_sequence_guards  # noqa: F401,E402

__all__ = [
    "assessments",
    "auth",
    "certificates",
    "classes",
    "companies",
    "courses",
    "enrollments",
    "lessons",
    "payments",
    "students",
]
