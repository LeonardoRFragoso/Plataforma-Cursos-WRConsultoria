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
"""

from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import func, select

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


async def audit_demo_data(*, execute: bool = False) -> dict:
    """Audit and optionally clean demo data. Returns a report dict."""
    async for db in get_db_privileged():
        # Demo users
        demo_users = (
            await db.execute(
                select(User).where(
                    User.email.like(f"%{DEMO_EMAIL_DOMAINS[0]}")
                    | User.email.like(f"%{DEMO_EMAIL_DOMAINS[1]}")
                )
            )
        ).scalars().all()

        # Demo classes
        demo_classes = (
            await db.execute(
                select(Class).where(Class.location == DEMO_CLASS_LOCATION)
            )
        ).scalars().all()

        # Demo certificates
        demo_certs = (
            await db.execute(
                select(Certificate).where(
                    Certificate.certificate_number.like(f"{DEMO_CERT_PREFIX}%")
                )
            )
        ).scalars().all()

        # Demo enrollments (via demo classes)
        demo_class_ids = [c.id for c in demo_classes]
        demo_enrollments = []
        if demo_class_ids:
            demo_enrollments = (
                await db.execute(
                    select(Enrollment).where(Enrollment.class_id.in_(demo_class_ids))
                )
            ).scalars().all()

        # Demo payments (via demo enrollments)
        demo_enrollment_ids = [e.id for e in demo_enrollments]
        demo_payments = []
        if demo_enrollment_ids:
            demo_payments = (
                await db.execute(
                    select(Payment).where(Payment.enrollment_id.in_(demo_enrollment_ids))
                )
            ).scalars().all()

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
        }

        if execute:
            if settings.ENVIRONMENT.lower() == "production":
                print("ABORT: ENVIRONMENT=production. Refusing to delete demo data.")
                sys.exit(1)
            if not settings.DEMO_SEED_MODE:
                print("ABORT: DEMO_SEED_MODE is not true. Refusing to delete demo data.")
                sys.exit(1)

            confirm = input("Type DELETE to confirm demo data removal: ")
            if confirm.strip().upper() != "DELETE":
                print("ABORT: Confirmation not provided. No data deleted.")
                sys.exit(0)

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
    print(f"DEMO DATA AUDIT REPORT")
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

    for item in report["demo_users"]:
        print(f"  USER: {item['email']} ({item['full_name']}, {item['role']})")
    for item in report["demo_classes"]:
        print(f"  CLASS: {item['location']} (course: {item['course_id']})")
    for item in report["demo_certificates"]:
        print(f"  CERT:  {item['number']} (enrollment: {item['enrollment_id']})")

    if not args.execute:
        print(f"\nTo delete: run with --execute (requires DEMO_SEED_MODE=true and ENVIRONMENT != production)")


if __name__ == "__main__":
    main()
