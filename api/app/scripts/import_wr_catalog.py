#!/usr/bin/env python3
"""Idempotent importer for the WR course catalog, content profiles, and materials.

Consumes the structured manifest at data/wr_course_content_manifest.json and
applies it to the database. Supports --dry-run (report only) and --apply
(execute changes).

Usage:
    python -m app.scripts.import_wr_catalog --dry-run
    python -m app.scripts.import_wr_catalog --apply

Idempotency:
    - Courses are matched by (tenant_id, code). Existing courses are updated,
      not duplicated.
    - Content profiles are matched by course_id. Existing profiles are updated.
    - Materials are matched by (tenant_id, course_id, sha256). Duplicate
      uploads are skipped.
    - Deactivation sets is_active=false on existing courses without deleting.

The importer does NOT:
    - Hard-delete courses with enrollments/payments/certificates
    - Upload PDF files to storage (use --upload-materials for that)
    - Modify financial or academic history
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.course import Course
from app.models.course_content_profile import CourseContentProfile
from app.models.course_material import CourseMaterial
from app.models.tenant import Tenant

MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "wr_course_content_manifest.json"


async def get_wr_tenant_id(db: AsyncSession) -> UUID | None:
    """Find the WR tenant by slug."""
    result = await db.execute(select(Tenant).where(Tenant.slug == "wr"))
    tenant = result.scalar_one_or_none()
    return tenant.id if tenant else None


async def import_catalog(db: AsyncSession, tenant_id: UUID, manifest: dict, dry_run: bool = True) -> dict:
    """Import/update courses from the manifest."""
    report = {
        "CREATE_COURSE": [],
        "UPDATE_COURSE": [],
        "DEACTIVATE_COURSE": [],
        "CREATE_CONTENT_PROFILE": [],
        "UPDATE_CONTENT_PROFILE": [],
        "CONFLICT": [],
        "REVIEW_REQUIRED": [],
        "SKIP_DUPLICATE": [],
    }

    # Get all existing courses for this tenant
    result = await db.execute(select(Course).where(Course.tenant_id == tenant_id))
    existing_courses = {c.code: c for c in result.scalars().all()}

    # Process each course in the manifest
    for entry in manifest["courses"]:
        code = entry["code"]
        content = entry["content"]
        action = entry["action"]

        if action == "UPDATE" and code in existing_courses:
            course = existing_courses[code]
            # Update name and description if we have better data
            updates = {}
            if entry["name"] and entry["name"] != course.name:
                updates["name"] = entry["name"]
            desc = content.get("short_description") or content.get("full_description")
            if desc and not course.description:
                updates["description"] = desc[:500]
            # Ensure course is active
            if not course.is_active:
                updates["is_active"] = True

            if updates:
                report["UPDATE_COURSE"].append({
                    "code": code,
                    "fields": list(updates.keys()),
                })
                if not dry_run:
                    for k, v in updates.items():
                        setattr(course, k, v)
            else:
                report["SKIP_DUPLICATE"].append({"code": code, "reason": "no changes"})

        elif action == "CREATE" and code not in existing_courses:
            desc = content.get("short_description") or content.get("full_description") or ""
            report["CREATE_COURSE"].append({"code": code, "name": entry["name"]})
            if not dry_run:
                course = Course(
                    tenant_id=tenant_id,
                    code=code,
                    name=entry["name"],
                    category=_get_category(entry["nr_family"]),
                    description=desc[:500] if desc else None,
                    carga_horaria=_get_ch(entry),
                    modality=_get_modality(entry),
                    price=_get_price(entry),
                    is_active=True,
                )
                db.add(course)
                await db.flush()
                existing_courses[code] = course

        elif action == "UPDATE" and code not in existing_courses:
            # UPDATE course doesn't exist in production — create it instead
            desc = content.get("short_description") or content.get("full_description") or ""
            report["CREATE_COURSE"].append({"code": code, "name": entry["name"], "note": "UPDATE→CREATE (not found in DB)"})
            if not dry_run:
                course = Course(
                    tenant_id=tenant_id,
                    code=code,
                    name=entry["name"],
                    category=_get_category(entry["nr_family"]),
                    description=desc[:500] if desc else None,
                    carga_horaria=_get_ch(entry),
                    modality=_get_modality(entry),
                    price=_get_price(entry),
                    is_active=True,
                )
                db.add(course)
                await db.flush()
                existing_courses[code] = course

        elif code in existing_courses and action == "CREATE":
            # Code already exists — treat as update
            report["CONFLICT"].append({
                "code": code,
                "reason": "CREATE action but code already exists — treating as UPDATE",
            })

        # Create/update content profile
        if code in existing_courses or not dry_run:
            course = existing_courses.get(code)
            if course:
                profile_data = _build_profile_data(content, entry)
                existing_profile = (
                    await db.execute(
                        select(CourseContentProfile).where(
                            CourseContentProfile.course_id == course.id,
                            CourseContentProfile.tenant_id == tenant_id,
                        )
                    )
                ).scalar_one_or_none()

                if existing_profile:
                    report["UPDATE_CONTENT_PROFILE"].append({"code": code})
                    if not dry_run:
                        for k, v in profile_data.items():
                            setattr(existing_profile, k, v)
                else:
                    report["CREATE_CONTENT_PROFILE"].append({"code": code})
                    if not dry_run:
                        profile = CourseContentProfile(
                            tenant_id=tenant_id,
                            course_id=course.id,
                            **profile_data,
                        )
                        db.add(profile)

        # Check for review required fields
        if entry.get("review_required_fields"):
            report["REVIEW_REQUIRED"].append({
                "code": code,
                "fields": entry["review_required_fields"],
            })

    # Deactivate old courses
    for code in manifest.get("deactivate_codes", []):
        if code in existing_courses:
            course = existing_courses[code]
            if course.is_active:
                report["DEACTIVATE_COURSE"].append({"code": code})
                if not dry_run:
                    course.is_active = False
        else:
            report["SKIP_DUPLICATE"].append({"code": code, "reason": "not found for deactivation"})

    if not dry_run:
        await db.commit()

    return report


def _get_category(nr_family: str) -> str:
    if nr_family.startswith("NR-"):
        return f"NR {nr_family.split('-')[1]}"
    if nr_family in ("PCA", "PPR", "PS"):
        return "Programas"
    if nr_family in ("DD", "GL", "BV"):
        return "Complementares"
    return "Outros"


def _get_ch(entry: dict) -> int:
    ch = entry["content"].get("workload")
    if ch and isinstance(ch, (int, float)):
        return int(ch)
    # Defaults
    nr = entry["nr_family"]
    if nr == "NR-10": return 40
    if nr == "NR-11": return 16
    if nr == "NR-20": return 16
    if nr == "NR-33": return 16
    if nr == "BV": return 16
    if nr == "NR-12": return 12
    if nr in ("NR-01", "NR-06", "NR-26", "PCA", "PPR", "GL"): return 4
    return 8


def _get_modality(entry: dict) -> str:
    mod = entry["content"].get("modality")
    if mod and isinstance(mod, str) and mod.upper() in ("PRESENCIAL", "EAD", "SEMIPRESENCIAL"):
        return mod.upper()
    nr = entry["nr_family"]
    if nr in ("NR-01", "NR-06", "NR-17", "NR-26", "PCA", "PPR", "GL"):
        return "EAD"
    return "SEMIPRESENCIAL"


def _get_price(entry: dict) -> float:
    nr = entry["nr_family"]
    if nr in ("NR-10",): return 299.90
    if nr in ("NR-11",): return 199.90
    if nr in ("NR-33", "BV"): return 249.90
    if nr in ("PCA", "PPR", "GL"): return 79.90
    if nr in ("PS", "DD"): return 149.90
    if nr.startswith("NR-"): return 149.90
    return 149.90


def _to_text(value) -> str | None:
    """Convert a value to a string suitable for Text columns, or None."""
    if value is None or value == "REVIEW_REQUIRED":
        return None
    if isinstance(value, list):
        return "; ".join(str(v) for v in value) if value else None
    return str(value)


def _build_profile_data(content: dict, entry: dict) -> dict:
    """Build CourseContentProfile fields from manifest content."""
    return {
        "short_description": _to_text(content.get("short_description")),
        "full_description": _to_text(content.get("full_description")),
        "target_audience": _to_text(content.get("target_audience")),
        "general_objective": _to_text(content.get("general_objective")),
        "specific_objectives": content.get("specific_objectives", []),
        "prerequisites": _to_text(content.get("prerequisites")),
        "learning_outcomes": content.get("learning_outcomes", []),
        "syllabus": content.get("syllabus", []),
        "modules": content.get("modules", []),
        "key_topics": content.get("key_topics", []),
        "risks_covered": content.get("risks_covered", []),
        "prevention_topics": content.get("prevention_topics", []),
        "ppe_topics": content.get("ppe_topics", []),
        "emergency_topics": content.get("emergency_topics", []),
        "standards_referenced": content.get("standards_referenced", []),
        "assessment_summary": _to_text(content.get("assessment_information")),
        "recycling_summary": _to_text(content.get("recycling_information")),
        "validity_summary": _to_text(content.get("validity_information")),
        "technical_responsible": _to_text(content.get("technical_responsible")),
        "instructor_information": content.get("instructor_information", []),
        "source_manifest": {
            "pdf": entry["source_pdf"]["filename"],
            "sha256": entry["source_pdf"]["sha256"],
            "pages": entry["source_pdf"]["pages"],
            "source_pages": content.get("source_pages"),
        },
        "review_status": entry.get("review_status", "INFERRED"),
        "review_required_fields": entry.get("review_required_fields", []),
    }


async def import_materials(db: AsyncSession, tenant_id: UUID, manifest: dict, dry_run: bool = True, upload: bool = False) -> dict:
    """Register course materials (metadata only — does not upload PDFs)."""
    report = {
        "UPLOAD_MATERIAL": [],
        "SKIP_DUPLICATE_MATERIAL": [],
    }

    if not upload:
        return report

    # Get all courses
    result = await db.execute(select(Course).where(Course.tenant_id == tenant_id))
    courses_by_code = {c.code: c for c in result.scalars().all()}

    for entry in manifest["courses"]:
        code = entry["code"]
        course = courses_by_code.get(code)
        if not course:
            continue

        sha = entry["source_pdf"]["sha256"]

        # Check if material already exists
        existing = (
            await db.execute(
                select(CourseMaterial).where(
                    CourseMaterial.course_id == course.id,
                    CourseMaterial.tenant_id == tenant_id,
                    CourseMaterial.sha256 == sha,
                )
            )
        ).scalar_one_or_none()

        if existing:
            report["SKIP_DUPLICATE_MATERIAL"].append({"code": code, "sha256": sha[:16]})
            continue

        # Create material record (storage_key will be set by upload process)
        storage_key = f"tenants/{tenant_id}/courses/{course.id}/materials/{entry['source_pdf']['filename']}"
        report["UPLOAD_MATERIAL"].append({"code": code, "sha256": sha[:16]})
        if not dry_run:
            material = CourseMaterial(
                tenant_id=tenant_id,
                course_id=course.id,
                title=f"Apostila — {entry['name']}",
                storage_key=storage_key,
                mime_type="application/pdf",
                size_bytes=entry["source_pdf"]["size_bytes"],
                sha256=sha,
                document_type="APOSTILA",
                is_active=True,
            )
            db.add(material)

    if not dry_run:
        await db.commit()

    return report


def print_report(report: dict, dry_run: bool):
    mode = "DRY RUN" if dry_run else "APPLIED"
    print(f"\n{'='*60}")
    print(f"  IMPORT REPORT — {mode}")
    print(f"{'='*60}")

    for action in ["CREATE_COURSE", "UPDATE_COURSE", "DEACTIVATE_COURSE",
                   "CREATE_CONTENT_PROFILE", "UPDATE_CONTENT_PROFILE",
                   "UPLOAD_MATERIAL", "SKIP_DUPLICATE_MATERIAL",
                   "CONFLICT", "REVIEW_REQUIRED"]:
        items = report.get(action, [])
        if items:
            print(f"\n  {action} ({len(items)}):")
            for item in items[:10]:
                print(f"    - {item}")
            if len(items) > 10:
                print(f"    ... and {len(items) - 10} more")

    print(f"\n{'='*60}")
    total = sum(len(v) for v in report.values())
    print(f"  Total actions: {total}")
    print(f"{'='*60}\n")


async def main():
    parser = argparse.ArgumentParser(description="Import WR course catalog from manifest")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no changes")
    parser.add_argument("--apply", action="store_true", help="Execute changes")
    parser.add_argument("--upload-materials", action="store_true", help="Also register material metadata")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("ERROR: must specify --dry-run or --apply")
        sys.exit(1)

    dry_run = args.dry_run

    if not MANIFEST_PATH.exists():
        print(f"ERROR: Manifest not found at {MANIFEST_PATH}")
        sys.exit(1)

    manifest = json.loads(MANIFEST_PATH.read_text())
    print(f"Loaded manifest: {len(manifest['courses'])} courses, {len(manifest.get('deactivate_codes', []))} to deactivate")

    async with AsyncSessionLocal() as db:
        tenant_id = await get_wr_tenant_id(db)
        if not tenant_id:
            print("ERROR: WR tenant not found")
            sys.exit(1)
        print(f"WR tenant ID: {tenant_id}")

        report = await import_catalog(db, tenant_id, manifest, dry_run=dry_run)

        if args.upload_materials:
            mat_report = await import_materials(db, tenant_id, manifest, dry_run=dry_run, upload=True)
            report.update(mat_report)

        print_report(report, dry_run)


if __name__ == "__main__":
    asyncio.run(main())
