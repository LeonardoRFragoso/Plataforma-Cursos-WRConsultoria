#!/usr/bin/env python3
"""Administrative script to issue a DEMONSTRATION certificate.

Produces a real, end-to-end academic journey (student → enrollment →
required lessons → progress → completed enrollment → certificate) and
emits a clearly-marked DEMO certificate (number prefixed ``DEMO-``)
that is impossible to confuse with an official one.

The script reuses the SAME issuance rule as the HTTP route
(``CertificateService.issue_certificate``) so business logic is never
duplicated. It does NOT bypass the "completed enrollment" requirement —
it simulates the full academic path first.

Idempotent: running twice reuses the existing demo user, student, class,
enrollment, lesson progress and certificate (deterministic lookup by
demo email + demo markers). It never creates duplicate records.

Usage:
    python -m app.scripts.create_demo_certificate --dry-run \
        --tenant-slug wr --course-code NR-01-F \
        --student-name "Aluno Demonstração WR"

    python -m app.scripts.create_demo_certificate --apply \
        --tenant-slug wr --course-code NR-01-F \
        --student-name "Aluno Demonstração WR"

Never run against production. The script refuses when ENVIRONMENT=production.
"""

import argparse
import asyncio
import os
import sys
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select

from app.core.config import settings
from app.core.context import current_tenant_id
from app.core.database import get_db_privileged
from app.core.demo_markers import CURRENT_DEMO_CLASS_LOCATION, CURRENT_DEMO_EMAIL_DOMAIN
from app.core.security import hash_password
from app.core.utils import utc_now
from app.models.certificate import Certificate
from app.models.class_model import Class, ClassStatus
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.lesson import Lesson, LessonContentType, LessonProgress
from app.models.student import Student
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.services.certificate_service import (
    CertificateService,
    is_demo_certificate,
)

# Demo markers are centralized in app.core.demo_markers.
# Generation uses the explicit CURRENT_* constants (never next(iter(frozenset))).
# Historical markers (wr.demo, alfa.demo, DEMO-EAD-ASSESSMENT) are recognized
# for detection but not used for generating new records.
DEMO_EMAIL_DOMAIN = CURRENT_DEMO_EMAIL_DOMAIN
DEMO_CLASS_LOCATION = CURRENT_DEMO_CLASS_LOCATION
DEMO_LESSON_TITLE_PREFIX = "[DEMO] "


def _demo_email(slug: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    return f"demo-certificado@{slug}.{DEMO_EMAIL_DOMAIN}"


def _refuse_production() -> None:
    env = (os.environ.get("ENVIRONMENT") or settings.ENVIRONMENT or "").lower()
    if env == "production":
        print("ERROR: refusing to run against production (ENVIRONMENT=production).")
        sys.exit(2)


async def _resolve_tenant(db, slug: str) -> Tenant:
    tenant = (
        await db.execute(select(Tenant).where(Tenant.slug == slug))
    ).scalar_one_or_none()
    if not tenant:
        raise SystemExit(f"Tenant with slug '{slug}' not found.")
    return tenant


async def _resolve_course(db, tenant_id: UUID, code: str) -> Course:
    course = (
        await db.execute(
            select(Course).where(
                Course.tenant_id == tenant_id,
                Course.code == code,
            )
        )
    ).scalar_one_or_none()
    if not course:
        raise SystemExit(f"Course with code '{code}' not found for tenant '{tenant_id}'.")
    if not course.is_active:
        raise SystemExit(f"Course '{code}' is inactive. Choose an active course.")
    return course


async def _resolve_admin(db, tenant_id: UUID) -> User:
    admin = (
        await db.execute(
            select(User)
            .where(User.tenant_id == tenant_id, User.role == UserRole.ADMIN)
            .order_by(User.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    if not admin:
        raise SystemExit("No admin user found for tenant; cannot assign responsible admin.")
    return admin


async def _get_or_create_demo_user(db, tenant_id: UUID, email: str, full_name: str):
    user = (
        await db.execute(select(User).where(User.tenant_id == tenant_id, User.email == email))
    ).scalar_one_or_none()
    if user:
        return user, False
    user = User(
        tenant_id=tenant_id,
        email=email,
        full_name=full_name,
        cpf=str(abs(hash(email)) % 10**11).zfill(11),
        password_hash=hash_password("demo-no-login"),
        role=UserRole.STUDENT,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user, True


async def _get_or_create_demo_student(db, tenant_id: UUID, user_id: UUID) -> Student:
    student = (
        await db.execute(select(Student).where(Student.user_id == user_id))
    ).scalar_one_or_none()
    if student:
        return student
    student = Student(
        tenant_id=tenant_id,
        user_id=user_id,
        cpf=str(abs(hash(str(user_id))) % 10**11).zfill(11),
    )
    db.add(student)
    await db.flush()
    return student


async def _get_or_create_demo_class(db, tenant_id: UUID, course_id: UUID, admin_id: UUID) -> Class:
    cls = (
        await db.execute(
            select(Class).where(
                Class.tenant_id == tenant_id,
                Class.course_id == course_id,
                Class.location == DEMO_CLASS_LOCATION,
            )
        )
    ).scalar_one_or_none()
    if cls:
        return cls
    start = utc_now().date()
    cls = Class(
        tenant_id=tenant_id,
        course_id=course_id,
        responsible_admin_id=admin_id,
        start_date=start,
        end_date=(utc_now() + timedelta(days=90)).date(),
        max_students=50,
        location=DEMO_CLASS_LOCATION,
        status=ClassStatus.ABERTA,
    )
    db.add(cls)
    await db.flush()
    return cls


async def _ensure_demo_lessons(db, tenant_id: UUID, course: Course):
    """Ensure the course has required lessons for a meaningful journey.

    If the course already has required lessons, they are reused as-is
    (real course content). If it has none, a small set of clearly-marked
    DEMO lessons is created so the academic path can be recorded. This
    never deletes or alters existing real lessons.
    """
    existing = (
        await db.execute(
            select(Lesson)
            .where(Lesson.tenant_id == tenant_id, Lesson.course_id == course.id)
            .order_by(Lesson.order)
        )
    ).scalars().all()
    required = [lesson for lesson in existing if lesson.is_required]
    if required:
        return required, False

    titles = ["Introdução", "Conteúdo principal", "Avaliação final"]
    created = []
    for idx, title in enumerate(titles):
        lesson = Lesson(
            tenant_id=tenant_id,
            course_id=course.id,
            title=f"{DEMO_LESSON_TITLE_PREFIX}{title}",
            description="Aula de demonstração — sem validade oficial.",
            order=idx,
            content_type=LessonContentType.YOUTUBE,
            duration_seconds=600,
            is_required=True,
        )
        db.add(lesson)
        created.append(lesson)
    await db.flush()
    return created, True


async def _get_or_create_enrollment(db, tenant_id: UUID, student_id: UUID, class_id: UUID, price: float):
    enrollment = (
        await db.execute(
            select(Enrollment).where(
                Enrollment.student_id == student_id,
                Enrollment.class_id == class_id,
            )
        )
    ).scalar_one_or_none()
    if enrollment:
        return enrollment, False
    enrollment = Enrollment(
        tenant_id=tenant_id,
        student_id=student_id,
        class_id=class_id,
        status=EnrollmentStatus.CONFIRMADA,
        price=price,
    )
    db.add(enrollment)
    await db.flush()
    return enrollment, True


async def _ensure_lesson_progress(db, tenant_id: UUID, student_id: UUID, lessons):
    """Record completion for every required lesson (idempotent)."""
    for lesson in lessons:
        existing = (
            await db.execute(
                select(LessonProgress).where(
                    LessonProgress.lesson_id == lesson.id,
                    LessonProgress.student_id == student_id,
                )
            )
        ).scalar_one_or_none()
        if existing:
            if not existing.completed:
                existing.completed = True
                existing.completed_at = utc_now()
            continue
        db.add(
            LessonProgress(
                tenant_id=tenant_id,
                lesson_id=lesson.id,
                student_id=student_id,
                watched_seconds=lesson.duration_seconds or 0,
                completed=True,
                completed_at=utc_now(),
            )
        )
    await db.flush()


async def _find_existing_demo_certificate(db, tenant_id: UUID, enrollment_id: UUID):
    """Return the active DEMO certificate for this enrollment if any."""
    certs = (
        await db.execute(
            select(Certificate)
            .where(
                Certificate.tenant_id == tenant_id,
                Certificate.enrollment_id == enrollment_id,
            )
            .order_by(Certificate.version.desc())
        )
    ).scalars().all()
    demo_active = next(
        (c for c in certs if c.status == "ACTIVE" and is_demo_certificate(c)), None
    )
    return demo_active, certs


async def run(*, dry_run: bool, tenant_slug: str, course_code: str, student_name: str, student_email: str | None):
    _refuse_production()
    print(f"=== Demo certificate issuance ({'DRY-RUN' if dry_run else 'APPLY'}) ===")

    async for db in get_db_privileged():
        token = current_tenant_id.set(None)
        try:
            tenant = await _resolve_tenant(db, tenant_slug)
            current_tenant_id.set(tenant.id)
            db.info["tenant_id"] = tenant.id

            course = await _resolve_course(db, tenant.id, course_code)
            admin = await _resolve_admin(db, tenant.id)
            email = _demo_email(tenant_slug, student_email)

            user, _user_created = await _get_or_create_demo_user(db, tenant.id, email, student_name)
            student = await _get_or_create_demo_student(db, tenant.id, user.id)
            cls = await _get_or_create_demo_class(db, tenant.id, course.id, admin.id)
            enrollment, _enr_created = await _get_or_create_enrollment(
                db, tenant.id, student.id, cls.id, course.price
            )
            lessons, lessons_created = await _ensure_demo_lessons(db, tenant.id, course)
            await _ensure_lesson_progress(db, tenant.id, student.id, lessons)

            # Complete the enrollment (the real certification prerequisite).
            enrollment.status = EnrollmentStatus.CONCLUIDA

            existing_demo, _all_certs = await _find_existing_demo_certificate(
                db, tenant.id, enrollment.id
            )

            print(f"  Tenant:        {tenant.name} ({tenant.slug})")
            print(f"  Course:        {course.code} — {course.name}")
            print(f"  Student:       {student_name} ({email})")
            print(f"  Lessons:       {len(lessons)} required "
                  f"({'created demo lessons' if lessons_created else 'reused existing'})")
            print(f"  Enrollment:    {enrollment.id} (status=CONCLUIDA)")

            if existing_demo:
                print(f"  Certificate:   REUSED active demo "
                      f"{existing_demo.certificate_number} (v{existing_demo.version})")
                print(f"  Validation:    {existing_demo.validation_code}")
                certificate = existing_demo
            else:
                if dry_run:
                    print("  Certificate:   WOULD CREATE new DEMO certificate")
                    print("  (run with --apply to emit it)")
                    return
                certificate = await CertificateService.issue_certificate(
                    db,
                    tenant_id=tenant.id,
                    enrollment=enrollment,
                    student=student,
                    course_id=course.id,
                    course_validity_days=course.certificate_validity_days,
                    actor_id=admin.id,
                    demo=True,
                    reason="Demonstração para apresentação executiva",
                )
                await db.commit()
                await db.refresh(certificate)
                print(f"  Certificate:   CREATED {certificate.certificate_number} (v{certificate.version})")
                print(f"  Validation:    {certificate.validation_code}")

            print()
            print(f"  Validation URL: {settings.FRONTEND_URL.rstrip('/')}"
                  f"/validar-certificado?codigo={certificate.validation_code}")
            print("  PDF download:   GET /api/v1/certificates/{id}/download (auth required)")
        finally:
            current_tenant_id.reset(token)


def main():
    parser = argparse.ArgumentParser(description="Issue a WR demonstration certificate.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report only; no DB writes.")
    parser.add_argument("--apply", action="store_true", help="Execute and persist changes.")
    parser.add_argument("--tenant-slug", default="wr", help="Tenant slug (default: wr).")
    parser.add_argument("--course-code", required=True, help="Course code, e.g. NR-01-F.")
    parser.add_argument("--student-name", default="Aluno Demonstração WR", help="Demo student full name.")
    parser.add_argument("--student-email", default=None, help="Override demo student email.")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        parser.error("choose either --dry-run or --apply")

    asyncio.run(
        run(
            dry_run=args.dry_run,
            tenant_slug=args.tenant_slug,
            course_code=args.course_code,
            student_name=args.student_name,
            student_email=args.student_email,
        )
    )


if __name__ == "__main__":
    main()
