#!/usr/bin/env python3
"""Audit demo/seed data in the database.

Lists users, classes, enrollments, certificates, and payments that are
clearly marked as demo/seed data. By default runs in --dry-run mode
(report only, no deletion).

Usage:
    python -m app.scripts.audit_demo_data [--execute]

--execute requires DEMO_SEED_MODE=true AND ENVIRONMENT != production,
and prompts for explicit confirmation. This script NEVER deletes
ambiguous data.

Safety features:
- AMBIGUOUS detection: data that matches some but not all demo markers
  is flagged as AMBIGUOUS and NEVER deleted, even with --execute.
- Transactional deletion: all deletes happen in a single transaction.
  If any delete fails, the entire operation rolls back.
- --execute guards: requires DEMO_SEED_MODE=true, ENVIRONMENT != production,
  and explicit "DELETE" confirmation.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db_privileged
from app.models.certificate import Certificate
from app.models.class_model import Class
from app.models.enrollment import Enrollment
from app.models.payment import Payment
from app.models.student import Student
from app.models.user import User

DEMO_CLASS_LOCATION = "DEMO-EAD"
DEMO_CERT_PREFIX = "DEMO-"
DEMO_EMAIL_DOMAINS = ("@wr.demo", "@alfa.demo")


def _is_unambiguous_demo_user(user: User) -> bool:
    """A user is unambiguously demo if email ends with a demo domain."""
    return any(user.email.endswith(d) for d in DEMO_EMAIL_DOMAINS)


def _is_unambiguous_demo_class(cls: Class) -> bool:
    """A class is unambiguously demo if location is DEMO-EAD."""
    return cls.location == DEMO_CLASS_LOCATION


def _is_unambiguous_demo_cert(cert: Certificate) -> bool:
    """A certificate is unambiguously demo if number starts with DEMO-."""
    return cert.certificate_number.startswith(DEMO_CERT_PREFIX)


async def audit_demo_data(*, execute: bool = False) -> dict:
    """Audit and optionally clean demo data. Returns a report dict.

    The report includes:
    - demo_*: lists of unambiguous demo data (safe to delete)
    - ambiguous_*: lists of data that matches some demo markers but not all
      (NEVER deleted, even with --execute)
    - deleted: whether deletion was performed
    """
    async for db in get_db_privileged():
        # Demo users (unambiguous)
        demo_users = (
            await db.execute(
                select(User).where(
                    User.email.like(f"%{DEMO_EMAIL_DOMAINS[0]}")
                    | User.email.like(f"%{DEMO_EMAIL_DOMAINS[1]}")
                )
            )
        ).scalars().all()

        # Demo classes (unambiguous)
        demo_classes = (
            await db.execute(
                select(Class).where(Class.location == DEMO_CLASS_LOCATION)
            )
        ).scalars().all()

        # Demo certificates (unambiguous)
        demo_certs = (
            await db.execute(
                select(Certificate).where(
                    Certificate.certificate_number.like(f"{DEMO_CERT_PREFIX}%")
                )
            )
        ).scalars().all()

        # Demo enrollments (via demo classes)
        demo_class_ids = {c.id for c in demo_classes}
        demo_enrollments = []
        if demo_class_ids:
            demo_enrollments = (
                await db.execute(
                    select(Enrollment).where(Enrollment.class_id.in_(demo_class_ids))
                )
            ).scalars().all()

        # Demo payments (via demo enrollments)
        demo_enrollment_ids = {e.id for e in demo_enrollments}
        demo_payments = []
        if demo_enrollment_ids:
            demo_payments = (
                await db.execute(
                    select(Payment).where(Payment.enrollment_id.in_(demo_enrollment_ids))
                )
            ).scalars().all()

        # AMBIGUOUS detection: certificates with DEMO- prefix but enrollment
        # is NOT in a demo class (could be a real certificate manually prefixed)
        ambiguous_certs = []
        for cert in demo_certs:
            enrollment = (
                await db.execute(
                    select(Enrollment).where(Enrollment.id == cert.enrollment_id)
                )
            ).scalar_one_or_none()
            if enrollment and enrollment.class_id not in demo_class_ids:
                ambiguous_certs.append({
                    "id": str(cert.id),
                    "number": cert.certificate_number,
                    "reason": "DEMO- prefix but enrollment is not in a demo class",
                })

        # AMBIGUOUS detection: demo email users with real enrollments
        # (enrollments in non-demo classes)
        demo_user_ids = {u.id for u in demo_users}
        ambiguous_users = []
        if demo_user_ids:
            real_enrollments = (
                await db.execute(
                    select(Enrollment)
                    .join(Student, Enrollment.student_id == Student.id)
                    .where(
                        Student.user_id.in_(demo_user_ids),
                        ~Enrollment.class_id.in_(demo_class_ids) if demo_class_ids else True,
                    )
                )
            ).scalars().all()
            for e in real_enrollments:
                student = (
                    await db.execute(
                        select(Student).where(Student.id == e.student_id)
                    )
                ).scalar_one_or_none()
                if student:
                    user = (
                        await db.execute(
                            select(User).where(User.id == student.user_id)
                        )
                    ).scalar_one_or_none()
                    if user:
                        ambiguous_users.append({
                            "id": str(user.id),
                            "email": user.email,
                            "reason": f"Demo email but has real enrollment {e.id}",
                        })

        report = {
            "demo_users": [
                {"id": str(u.id), "email": u.email, "full_name": u.full_name, "role": u.role}
                for u in demo_users
            ],
            "demo_classes": [
                {"id": str(c.id), "location": c.location, "course_id": str(c.course_id)}
                for c in demo_classes
            ],
            "demo_enrollments": [
                {"id": str(e.id), "student_id": str(e.student_id), "class_id": str(e.class_id)}
                for e in demo_enrollments
            ],
            "demo_certificates": [
                {"id": str(c.id), "number": c.certificate_number, "enrollment_id": str(c.enrollment_id)}
                for c in demo_certs
            ],
            "demo_payments": [
                {"id": str(p.id), "enrollment_id": str(p.enrollment_id), "status": str(p.status)}
                for p in demo_payments
            ],
            "ambiguous_certificates": ambiguous_certs,
            "ambiguous_users": ambiguous_users,
        }

        if execute:
            if settings.ENVIRONMENT.lower() == "production":
                print("ABORT: ENVIRONMENT=production. Refusing to delete demo data.")
                sys.exit(1)
            if not settings.DEMO_SEED_MODE:
                print("ABORT: DEMO_SEED_MODE is not true. Refusing to delete demo data.")
                sys.exit(1)

            # AMBIGUOUS data is NEVER deleted — even with --execute
            if ambiguous_certs or ambiguous_users:
                print(
                    f"ABORT: {len(ambiguous_certs)} ambiguous certificate(s) and "
                    f"{len(ambiguous_users)} ambiguous user(s) detected. "
                    "Refusing to delete any data. Review the ambiguous items first."
                )
                sys.exit(1)

            confirm = input("Type DELETE to confirm demo data removal: ")
            if confirm.strip().upper() != "DELETE":
                print("ABORT: Confirmation not provided. No data deleted.")
                sys.exit(0)

            # Transactional deletion: all deletes in a single transaction.
            # If any delete fails, the entire operation rolls back.
            try:
                # Delete in dependency order: payments → certificates → enrollments → classes → users
                for p in demo_payments:
                    await db.delete(p)
                for c in demo_certs:
                    await db.delete(c)
                for e in demo_enrollments:
                    await db.delete(e)
                for c in demo_classes:
                    await db.delete(c)
                for u in demo_users:
                    # Delete student records too
                    student = await db.scalar(select(Student).where(Student.user_id == u.id))
                    if student:
                        await db.delete(student)
                    await db.delete(u)
                await db.commit()
                report["deleted"] = True
            except Exception as exc:  # noqa: BLE001 — intentional: rollback on any failure
                await db.rollback()
                print(f"ABORT: Deletion failed, transaction rolled back: {exc}")
                report["deleted"] = False
                report["error"] = str(exc)
                return report
        else:
            report["deleted"] = False

        return report


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Audit demo data")
    parser.add_argument("--execute", action="store_true", help="Delete demo data (requires confirmation)")
    args = parser.parse_args()

    report = asyncio.run(audit_demo_data(execute=args.execute))

    print(f"\n{'='*60}")
    print("DEMO DATA AUDIT REPORT")
    print(f"{'='*60}")
    print(f"Mode: {'EXECUTE (delete)' if args.execute else 'DRY-RUN (report only)'}")
    print(f"Deleted: {report['deleted']}")
    print(f"{'='*60}")
    print(f"Demo users:         {len(report['demo_users'])}")
    print(f"Demo classes:       {len(report['demo_classes'])}")
    print(f"Demo enrollments:   {len(report['demo_enrollments'])}")
    print(f"Demo certificates:  {len(report['demo_certificates'])}")
    print(f"Demo payments:      {len(report['demo_payments'])}")
    print(f"{'='*60}")
    print("AMBIGUOUS (NEVER deleted):")
    print(f"  Ambiguous certs:  {len(report.get('ambiguous_certificates', []))}")
    print(f"  Ambiguous users:  {len(report.get('ambiguous_users', []))}")
    print(f"{'='*60}")

    for item in report["demo_users"]:
        print(f"  USER: {item['email']} ({item['full_name']}, {item['role']})")
    for item in report["demo_classes"]:
        print(f"  CLASS: {item['location']} (course: {item['course_id']})")
    for item in report["demo_certificates"]:
        print(f"  CERT:  {item['number']} (enrollment: {item['enrollment_id']})")
    for item in report.get("ambiguous_certificates", []):
        print(f"  AMBIGUOUS CERT: {item['number']} — {item['reason']}")
    for item in report.get("ambiguous_users", []):
        print(f"  AMBIGUOUS USER: {item['email']} — {item['reason']}")

    if not args.execute:
        print("\nTo delete: run with --execute (requires DEMO_SEED_MODE=true and ENVIRONMENT != production)")
    if report.get("ambiguous_certificates") or report.get("ambiguous_users"):
        print("\nWARNING: Ambiguous data detected. --execute will REFUSE to delete until ambiguous items are resolved.")


if __name__ == "__main__":
    main()
