#!/usr/bin/env python3
"""Audit and conservatively repair enrolled classes that point to courses without lessons.

This script exists for a production failure mode where a student is enrolled in a
class whose ``course_id`` references a catalog/legacy course record with zero lessons,
while another course in the same tenant represents the same training and owns the
uploaded lesson rows.

Safety rules
------------
- Dry-run is the default behavior. ``--apply`` is explicit.
- ``--apply`` requires ``--student-email`` to limit the blast radius.
- A class is auto-repairable only when there is exactly one lesson-bearing course
  with the exact same normalized name in the same tenant.
- Completed enrollments, classes with a pinned pedagogical project, and enrollments
  that already have certificates are never changed automatically.
- Ambiguous matches are reported for manual review and never modified.
- The script changes only ``Class.course_id``. It does not touch enrollments,
  progress, certificates, lessons, storage keys, payments, or users.

Examples
--------
    python -m app.scripts.audit_repair_enrollment_course_links --student-email aluno@example.com
    python -m app.scripts.audit_repair_enrollment_course_links --student-email aluno@example.com --apply

The command is idempotent: after a successful repair, the class points to a course
with lessons and will no longer be classified as broken on the next run.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.certificate import Certificate
from app.models.class_model import Class
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.lesson import Lesson
from app.models.student import Student
from app.models.tenant import Tenant
from app.models.user import User


@dataclass
class Candidate:
    course_id: str
    code: str
    name: str
    lesson_count: int
    exact_name: bool
    similarity: float


@dataclass
class AuditItem:
    enrollment_id: str
    enrollment_status: str
    class_id: str
    current_course_id: str
    current_course_code: str
    current_course_name: str
    current_lesson_count: int
    candidate: Candidate | None
    alternatives: list[Candidate]
    action: str
    reason: str


def _normalize(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower().replace("–", "-").replace("—", "-")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _similarity(left: str | None, right: str | None) -> float:
    return round(SequenceMatcher(None, _normalize(left), _normalize(right)).ratio(), 4)


async def _get_tenant_id(db: AsyncSession, slug: str) -> UUID:
    tenant = (
        await db.execute(select(Tenant).where(Tenant.slug == slug))
    ).scalar_one_or_none()
    if not tenant:
        raise RuntimeError(f"Tenant '{slug}' not found")
    return tenant.id


async def _lesson_counts(db: AsyncSession, tenant_id: UUID) -> dict[UUID, int]:
    rows = (
        await db.execute(
            select(Lesson.course_id, func.count(Lesson.id))
            .where(Lesson.tenant_id == tenant_id)
            .group_by(Lesson.course_id)
        )
    ).all()
    return {course_id: int(count) for course_id, count in rows}


async def _student(db: AsyncSession, tenant_id: UUID, email: str) -> Student | None:
    return (
        await db.execute(
            select(Student)
            .join(User, User.id == Student.user_id)
            .where(
                Student.tenant_id == tenant_id,
                User.tenant_id == tenant_id,
                func.lower(User.email) == email.lower(),
            )
        )
    ).scalar_one_or_none()


async def _certificate_enrollment_ids(
    db: AsyncSession,
    tenant_id: UUID,
    enrollment_ids: list[UUID],
) -> set[UUID]:
    if not enrollment_ids:
        return set()
    rows = (
        await db.execute(
            select(Certificate.enrollment_id).where(
                Certificate.tenant_id == tenant_id,
                Certificate.enrollment_id.in_(enrollment_ids),
            )
        )
    ).scalars().all()
    return set(rows)


def _candidate_list(source: Course, lesson_courses: list[tuple[Course, int]]) -> list[Candidate]:
    source_name = _normalize(source.name)
    candidates: list[Candidate] = []
    for course, count in lesson_courses:
        if course.id == source.id:
            continue
        exact_name = bool(source_name) and source_name == _normalize(course.name)
        similarity = _similarity(source.name, course.name)
        if exact_name or similarity >= 0.72:
            candidates.append(
                Candidate(
                    course_id=str(course.id),
                    code=course.code,
                    name=course.name,
                    lesson_count=count,
                    exact_name=exact_name,
                    similarity=similarity,
                )
            )
    candidates.sort(key=lambda item: (not item.exact_name, -item.similarity, item.code))
    return candidates


async def audit(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    student_email: str | None,
    apply: bool,
) -> dict:
    counts = await _lesson_counts(db, tenant_id)
    courses = (
        await db.execute(select(Course).where(Course.tenant_id == tenant_id))
    ).scalars().all()
    courses_by_id = {course.id: course for course in courses}
    lesson_courses = [(course, counts.get(course.id, 0)) for course in courses if counts.get(course.id, 0) > 0]

    enrollment_stmt = (
        select(Enrollment, Class)
        .join(Class, Class.id == Enrollment.class_id)
        .where(
            Enrollment.tenant_id == tenant_id,
            Class.tenant_id == tenant_id,
            Enrollment.status.in_([
                EnrollmentStatus.PENDENTE,
                EnrollmentStatus.CONFIRMADA,
                EnrollmentStatus.CONCLUIDA,
            ]),
        )
        .order_by(Enrollment.created_at, Enrollment.id)
    )

    selected_student = None
    if student_email:
        selected_student = await _student(db, tenant_id, student_email)
        if not selected_student:
            raise RuntimeError(f"Student not found for email: {student_email}")
        enrollment_stmt = enrollment_stmt.where(Enrollment.student_id == selected_student.id)

    rows = (await db.execute(enrollment_stmt)).all()
    enrollment_ids = [enrollment.id for enrollment, _cls in rows]
    certificate_ids = await _certificate_enrollment_ids(db, tenant_id, enrollment_ids)

    items: list[AuditItem] = []
    classes_to_update: dict[UUID, UUID] = {}
    class_enrollments: dict[UUID, list[Enrollment]] = defaultdict(list)
    for enrollment, cls in rows:
        class_enrollments[cls.id].append(enrollment)

    for enrollment, cls in rows:
        course = courses_by_id.get(cls.course_id)
        if not course:
            items.append(
                AuditItem(
                    enrollment_id=str(enrollment.id),
                    enrollment_status=enrollment.status.value,
                    class_id=str(cls.id),
                    current_course_id=str(cls.course_id),
                    current_course_code="UNKNOWN",
                    current_course_name="UNKNOWN",
                    current_lesson_count=0,
                    candidate=None,
                    alternatives=[],
                    action="REVIEW_REQUIRED",
                    reason="Class references a course that was not found in this tenant.",
                )
            )
            continue

        current_count = counts.get(course.id, 0)
        if current_count > 0:
            items.append(
                AuditItem(
                    enrollment_id=str(enrollment.id),
                    enrollment_status=enrollment.status.value,
                    class_id=str(cls.id),
                    current_course_id=str(course.id),
                    current_course_code=course.code,
                    current_course_name=course.name,
                    current_lesson_count=current_count,
                    candidate=None,
                    alternatives=[],
                    action="OK",
                    reason="The enrolled class already points to a course with lessons.",
                )
            )
            continue

        alternatives = _candidate_list(course, lesson_courses)
        exact = [candidate for candidate in alternatives if candidate.exact_name]
        candidate = exact[0] if len(exact) == 1 else None

        all_class_enrollments = class_enrollments[cls.id]
        has_completed = any(item.status == EnrollmentStatus.CONCLUIDA for item in all_class_enrollments)
        has_certificate = any(item.id in certificate_ids for item in all_class_enrollments)
        has_pinned_project = cls.pedagogical_project_version_id is not None

        if len(exact) > 1:
            action = "REVIEW_REQUIRED"
            reason = "More than one lesson-bearing course has the same normalized name."
        elif not candidate:
            action = "REVIEW_REQUIRED"
            reason = "No unique exact-name lesson-bearing course could be inferred safely."
        elif has_completed:
            action = "REVIEW_REQUIRED"
            reason = "Class has a completed enrollment; historical course linkage will not be rewritten automatically."
        elif has_certificate:
            action = "REVIEW_REQUIRED"
            reason = "Class has an enrollment with a certificate; automatic relinking is blocked."
        elif has_pinned_project:
            action = "REVIEW_REQUIRED"
            reason = "Class pins a pedagogical project version; automatic relinking is blocked."
        else:
            action = "WOULD_RELINK"
            reason = "Unique exact-name lesson-bearing course found and safety gates passed."
            classes_to_update[cls.id] = UUID(candidate.course_id)

        items.append(
            AuditItem(
                enrollment_id=str(enrollment.id),
                enrollment_status=enrollment.status.value,
                class_id=str(cls.id),
                current_course_id=str(course.id),
                current_course_code=course.code,
                current_course_name=course.name,
                current_lesson_count=current_count,
                candidate=candidate,
                alternatives=alternatives[:5],
                action=action,
                reason=reason,
            )
        )

    applied: list[dict] = []
    if apply:
        for class_id, target_course_id in classes_to_update.items():
            cls = next(cls for _enrollment, cls in rows if cls.id == class_id)
            old_course_id = cls.course_id
            cls.course_id = target_course_id
            applied.append({
                "class_id": str(class_id),
                "from_course_id": str(old_course_id),
                "to_course_id": str(target_course_id),
            })
        await db.commit()

    return {
        "tenant_id": str(tenant_id),
        "student_email": student_email,
        "student_id": str(selected_student.id) if selected_student else None,
        "mode": "APPLY" if apply else "DRY_RUN",
        "enrollments_checked": len(rows),
        "courses_with_lessons": len(lesson_courses),
        "repairable_classes": len(classes_to_update),
        "applied": applied,
        "items": [asdict(item) for item in items],
    }


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit/repair enrolled classes that reference courses without lessons"
    )
    parser.add_argument("--tenant-slug", default="wr")
    parser.add_argument("--student-email", help="Limit audit/repair to one student")
    parser.add_argument("--apply", action="store_true", help="Apply safe inferred relinks")
    args = parser.parse_args()

    if args.apply and not args.student_email:
        print("ERROR: --apply requires --student-email to limit the blast radius", file=sys.stderr)
        sys.exit(2)

    async with AsyncSessionLocal() as db:
        try:
            tenant_id = await _get_tenant_id(db, args.tenant_slug)
            report = await audit(
                db,
                tenant_id,
                student_email=args.student_email,
                apply=args.apply,
            )
        except Exception as exc:
            if args.apply:
                await db.rollback()
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
