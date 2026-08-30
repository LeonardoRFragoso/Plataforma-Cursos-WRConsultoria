"""Historical migration contract test.

Validates that the demo markers used by migration
``a0b1c2d3e4f5_enroll_demo_student_in_uploaded_courses`` are recognized
by the current demo classifier. This prevents drift between historical
demo data and the classifier.

This test reads the migration file statically (no database, no execution)
and checks that the constants defined there are present in the shared
demo markers module.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.demo_markers import (
    DEMO_CLASS_LOCATIONS,
    DEMO_EMAIL_DOMAINS,
)

MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "a0b1c2d3e4f5_enroll_demo_student_in_uploaded_courses.py"
)


def _extract_constant(source: str, name: str) -> str | None:
    """Extract a string constant value from Python source code."""
    pattern = rf'^{name}\s*=\s*["\']([^"\']+)["\']'
    match = re.search(pattern, source, re.MULTILINE)
    return match.group(1) if match else None


def _extract_tuple_constant(source: str, name: str) -> list[str] | None:
    """Extract a tuple of string constants from Python source code."""
    pattern = rf'^{name}\s*=\s*\(([^)]+)\)'
    match = re.search(pattern, source, re.MULTILINE)
    if not match:
        return None
    raw = match.group(1)
    items = re.findall(r'["\']([^"\']+)["\']', raw)
    return items if items else None


def test_migration_file_exists():
    """The historical migration file must exist."""
    assert MIGRATION_PATH.exists(), f"Migration file not found: {MIGRATION_PATH}"


def test_migration_revision_id():
    """The migration revision must be a0b1c2d3e4f5."""
    source = MIGRATION_PATH.read_text()
    assert 'revision: str = "a0b1c2d3e4f5"' in source


def test_migration_demo_email_recognized():
    """The DEMO_EMAIL from the migration must be recognized by the classifier."""
    source = MIGRATION_PATH.read_text()
    demo_email = _extract_constant(source, "DEMO_EMAIL")
    assert demo_email is not None, "DEMO_EMAIL constant not found in migration"
    # Extract domain from email
    domain = demo_email.split("@")[-1].lower()
    assert domain in DEMO_EMAIL_DOMAINS, (
        f"Migration DEMO_EMAIL domain '{domain}' is not in DEMO_EMAIL_DOMAINS. "
        f"The classifier will not recognize historical demo enrollments."
    )


def test_migration_class_location_recognized():
    """The CLASS_LOCATION from the migration must be recognized by the classifier."""
    source = MIGRATION_PATH.read_text()
    class_location = _extract_constant(source, "CLASS_LOCATION")
    assert class_location is not None, "CLASS_LOCATION constant not found in migration"
    assert class_location in DEMO_CLASS_LOCATIONS, (
        f"Migration CLASS_LOCATION '{class_location}' is not in DEMO_CLASS_LOCATIONS. "
        f"The classifier will not recognize historical demo classes."
    )


def test_migration_course_codes_include_expected():
    """The COURSE_CODES tuple must include the 4 expected courses."""
    source = MIGRATION_PATH.read_text()
    course_codes = _extract_tuple_constant(source, "COURSE_CODES")
    assert course_codes is not None, "COURSE_CODES constant not found in migration"
    expected = {"NR-06-F", "NR-12-F", "NR-33-AUT", "NR-35-F"}
    actual = set(course_codes)
    assert expected.issubset(actual), (
        f"Migration COURSE_CODES {actual} does not include all expected: {expected}"
    )


def test_migration_price_is_zero():
    """The migration must insert enrollments with price=0.0."""
    source = MIGRATION_PATH.read_text()
    assert "0.0" in source, "Migration does not appear to set price=0.0"


def test_migration_not_modified_by_classifier_fix():
    """The migration should not import from app.core.demo_markers.

    Historical migrations are immutable and must not depend on runtime
    modules. The classifier recognizes the migration's markers without
    the migration needing to import anything.
    """
    source = MIGRATION_PATH.read_text()
    assert "demo_markers" not in source, (
        "Migration should not import from app.core.demo_markers — "
        "historical migrations are immutable."
    )
