from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance import CourseComplianceProfile
from app.models.course import Course
from app.services.regulatory_rule_registry import (
    CONSERVATIVE_TWO_YEAR_BUFFER_DAYS,
    NR1_CURRENT,
    operational_ead_access_log_retention_days,
)


@dataclass(frozen=True)
class RetentionRequirements:
    minimum_training_event_retention_days: int | None
    unresolved_course_codes: tuple[str, ...]
    source_code: str = NR1_CURRENT.code
    source_url: str = NR1_CURRENT.source_url
    rule: str = "EAD access logs: retain through course validity end + 2 calendar years"
    operational_conversion: str = (
        "validity days + 731 conservative day buffer; validity months are "
        "projected as 31 days each"
    )
    automatic_deletion_enabled: bool = False

    @property
    def resolved(self) -> bool:
        return not self.unresolved_course_codes

    def public_dict(self) -> dict:
        return {
            "minimum_training_event_retention_days": self.minimum_training_event_retention_days,
            "unresolved_course_codes": list(self.unresolved_course_codes),
            "source_code": self.source_code,
            "source_url": self.source_url,
            "rule": self.rule,
            "operational_conversion": self.operational_conversion,
            "automatic_deletion_enabled": self.automatic_deletion_enabled,
            "resolved": self.resolved,
        }


def operational_validity_days(
    certificate_validity_days: int | None,
    validity_period_months: int | None,
) -> int | None:
    """Return the safest available validity projection for policy enforcement.

    The catalog may express validity in days while compliance metadata may use
    months. If both exist, use the larger value so a stale/shorter field cannot
    silently reduce the retention floor. Months use 31 days conservatively.
    """
    candidates: list[int] = []
    if certificate_validity_days and certificate_validity_days > 0:
        candidates.append(int(certificate_validity_days))
    if validity_period_months and validity_period_months > 0:
        candidates.append(int(validity_period_months) * 31)
    return max(candidates) if candidates else None


def build_retention_requirements(rows) -> RetentionRequirements:
    minimum: int | None = None
    unresolved: set[str] = set()

    for course, profile in rows:
        delivery_mode = str(profile.delivery_mode or "").strip().upper()
        if delivery_mode not in {"EAD", "SEMIPRESENCIAL"}:
            continue

        validity_days = operational_validity_days(
            getattr(course, "certificate_validity_days", None),
            getattr(profile, "validity_period_months", None),
        )
        if validity_days is None:
            unresolved.add(str(course.code))
            continue

        floor = operational_ead_access_log_retention_days(validity_days)
        minimum = floor if minimum is None else max(minimum, floor)

    return RetentionRequirements(
        minimum_training_event_retention_days=minimum,
        unresolved_course_codes=tuple(sorted(unresolved)),
    )


async def calculate_tenant_retention_requirements(
    db: AsyncSession,
    tenant_id: UUID,
) -> RetentionRequirements:
    rows = (
        await db.execute(
            select(Course, CourseComplianceProfile)
            .join(
                CourseComplianceProfile,
                (CourseComplianceProfile.course_id == Course.id)
                & (CourseComplianceProfile.tenant_id == tenant_id),
            )
            .where(
                Course.tenant_id == tenant_id,
                Course.is_active.is_(True),
            )
        )
    ).all()
    return build_retention_requirements(rows)


def retention_policy_violations(
    training_event_retention_days: int | None,
    requirements: RetentionRequirements,
) -> list[str]:
    violations: list[str] = []
    if requirements.unresolved_course_codes:
        violations.append(
            "RETENTION_VALIDITY_UNRESOLVED: "
            + ", ".join(requirements.unresolved_course_codes)
        )

    floor = requirements.minimum_training_event_retention_days
    if floor is not None and (
        training_event_retention_days is None
        or training_event_retention_days < floor
    ):
        violations.append(
            "TRAINING_EVENT_RETENTION_BELOW_NORMATIVE_FLOOR: "
            f"required>={floor}, configured={training_event_retention_days}"
        )
    return violations


def conservative_two_year_buffer_days() -> int:
    """Expose the projection for tests/diagnostics without duplicating magic numbers."""
    return CONSERVATIVE_TWO_YEAR_BUFFER_DAYS
