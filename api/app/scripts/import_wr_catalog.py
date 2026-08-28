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
import hashlib
import json
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.compliance import ComplianceStatus, CourseComplianceProfile, WorkloadSource
from app.models.course import Course
from app.models.course_content_profile import CourseContentProfile, ReviewStatus
from app.models.course_material import CourseMaterial
from app.models.tenant import Tenant

MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "wr_course_content_manifest.json"

# Approval source recorded when the owner has externally confirmed the
# academic content extracted from the apostilas. This does NOT approve
# workload, modality, practice, recycling, or technical responsible.
OWNER_EXTERNAL_CONFIRMATION = "OWNER_EXTERNAL_CONFIRMATION"


def compute_manifest_hash(manifest_bytes: bytes) -> str:
    """Deterministic SHA-256 of the manifest file bytes."""
    return hashlib.sha256(manifest_bytes).hexdigest()


def compute_manifest_version(manifest_path: Path) -> str:
    """Version identifier for the manifest = filename + size + mtime."""
    stat = manifest_path.stat()
    return f"{manifest_path.name}:{stat.st_size}:{int(stat.st_mtime)}"


async def get_wr_tenant_id(db: AsyncSession) -> UUID | None:
    """Find the WR tenant by slug."""
    result = await db.execute(select(Tenant).where(Tenant.slug == "wr"))
    tenant = result.scalar_one_or_none()
    return tenant.id if tenant else None


async def import_catalog(db: AsyncSession, tenant_id: UUID, manifest: dict, dry_run: bool = True, manifest_hash: str = "", manifest_version: str = "") -> dict:
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
                profile_data = _build_profile_data(content, entry, manifest_hash, manifest_version)
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
    """Get course workload in hours from the manifest content.

    Uses the explicit workload from the manifest if present. Otherwise
    falls back to employer-defined defaults that are NOT normative minimums —
    they are WR's operational configuration and must not be treated as
    legal minimums. The regulatory compliance profile tracks the
    authoritative workload_source and normative_minimum_minutes separately.
    """
    ch = entry["content"].get("workload")
    if ch and isinstance(ch, (int, float)):
        return int(ch)
    # Employer-defined operational defaults (NOT normative minimums)
    nr = entry["nr_family"]
    if nr == "NR-10": return 40
    if nr == "NR-11": return 16
    if nr == "NR-20": return 16
    if nr == "NR-33": return 16
    if nr == "BV": return 16
    if nr == "NR-12": return 12
    if nr in ("NR-01", "NR-06", "NR-26", "PCA", "PPR", "GL"): return 4
    return 8


# Regulatory workload metadata for the 14 priority courses.
# Maps course code to (workload_source, normative_minimum_minutes, modality_override).
# normative_minimum_minutes is None when no universal legal minimum exists.
REGULATORY_WORKLOAD: dict[str, dict] = {
    "NR-10-B": {
        "workload_source": "NORMATIVE_MINIMUM",
        "normative_minimum_minutes": 40 * 60,
        "modality": "SEMIPRESENCIAL",
    },
    "NR-10-S": {
        "workload_source": "NORMATIVE_MINIMUM",
        "normative_minimum_minutes": 40 * 60,
        "modality": "SEMIPRESENCIAL",
        "prerequisite": "NR-10-B",
    },
    "NR-33-AUT": {
        "workload_source": "NORMATIVE_MINIMUM",
        "normative_minimum_minutes": 16 * 60,
        "periodic_minutes": 8 * 60,
        "validity_months": 12,
        "modality": "PRESENCIAL",
        "requires_practical_component": True,
        "min_practical_percent": 50,
    },
    "NR-33-SUP": {
        "workload_source": "NORMATIVE_MINIMUM",
        "normative_minimum_minutes": 40 * 60,
        "periodic_minutes": 8 * 60,
        "validity_months": 12,
        "modality": "PRESENCIAL",
        "requires_practical_component": True,
        "min_practical_percent": 50,
    },
    "NR-35-F": {
        "workload_source": "NORMATIVE_MINIMUM",
        "normative_minimum_minutes": 8 * 60,
        "periodic_minutes": 8 * 60,
        "validity_months": 24,
        "modality": "PRESENCIAL",
        "requires_practical_component": True,
    },
    "NR-18-F": {
        # NR-18-F variant is NOT confirmed as "Treinamento Básico" by the
        # owner/CEO. Until explicit human confirmation, all regulatory
        # rules remain REVIEW_REQUIRED. Do NOT infer 4h/24 months/Básico
        # just because the code contains NR-18.
        "workload_source": "REVIEW_REQUIRED",
        "normative_minimum_minutes": None,
        "modality": None,  # do not override — let manifest/default decide
        "status": "REVIEW_REQUIRED",
    },
    "NR-06-F": {
        # NR-06 has no universal 4h legal minimum. Workload is employer-defined.
        "workload_source": "EMPLOYER_DEFINED",
        "normative_minimum_minutes": None,
        "modality": "EAD",
    },
    "NR-12-F": {
        # NR-12 workload is defined by PLH (Profissional Legalmente Habilitado)
        "workload_source": "PLH_DEFINED",
        "normative_minimum_minutes": None,
        "modality": "SEMIPRESENCIAL",
        "requires_practical_component": True,
    },
    # NR-11 variants — employer/PLH-defined, not 16h legal minimum
    "NR-11-EMP": {"workload_source": "EMPLOYER_DEFINED", "normative_minimum_minutes": None, "modality": "SEMIPRESENCIAL", "requires_practical_component": True},
    "NR-11-GUI": {"workload_source": "EMPLOYER_DEFINED", "normative_minimum_minutes": None, "modality": "SEMIPRESENCIAL", "requires_practical_component": True},
    "NR-11-MIN": {"workload_source": "EMPLOYER_DEFINED", "normative_minimum_minutes": None, "modality": "SEMIPRESENCIAL", "requires_practical_component": True},
    "NR-11-PLA": {"workload_source": "EMPLOYER_DEFINED", "normative_minimum_minutes": None, "modality": "SEMIPRESENCIAL", "requires_practical_component": True},
    "NR-11-PON": {"workload_source": "EMPLOYER_DEFINED", "normative_minimum_minutes": None, "modality": "SEMIPRESENCIAL", "requires_practical_component": True},
    "NR-11-RET": {"workload_source": "EMPLOYER_DEFINED", "normative_minimum_minutes": None, "modality": "SEMIPRESENCIAL", "requires_practical_component": True},
}


def _get_modality(entry: dict) -> str:
    # Check regulatory override first (e.g. NR-33, NR-35 require PRESENCIAL).
    # A None modality in REGULATORY_WORKLOAD means "do not override" (NR-18-F).
    code = entry.get("code", "")
    reg = REGULATORY_WORKLOAD.get(code, {})
    reg_modality = reg.get("modality")
    if reg_modality is not None:
        return reg_modality
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


# NR family → regulatory_standard mapping for compliance profiles.
_NR_STANDARD = {
    "NR-10": ("NR-10", "Segurança em Instalações e Serviços em Eletricidade"),
    "NR-11": ("NR-11", "Transporte, Movimentação, Armazenagem e Manuseio de Materiais"),
    "NR-12": ("NR-12", "Segurança no Trabalho em Máquinas e Equipamentos"),
    "NR-18": ("NR-18", "Condições e Meio Ambiente de Trabalho na Indústria da Construção"),
    "NR-33": ("NR-33", "Trabalho em Espaço Confinado"),
    "NR-35": ("NR-35", "Trabalho em Altura"),
    "NR-06": ("NR-06", "Equipamento de Proteção Individual"),
}


async def upsert_regulatory_compliance_profile(
    db: AsyncSession,
    tenant_id: UUID,
    course: Course,
    entry: dict,
) -> CourseComplianceProfile | None:
    """Idempotently upsert a CourseComplianceProfile from REGULATORY_WORKLOAD.

    Only updates fields managed by the regulatory matrix. Does NOT
    overwrite manually-approved fields (technical_responsible_id,
    pedagogical_project_version_id, certificate_required_fields,
    next_compliance_review_at, minimum_score).

    Returns the profile, or None if the course code has no regulatory
    matrix entry.
    """
    code = entry.get("code", "")
    reg = REGULATORY_WORKLOAD.get(code)
    if reg is None:
        return None

    nr_family = entry.get("nr_family", "")
    standard, version = _NR_STANDARD.get(nr_family, (nr_family, "REVIEW_REQUIRED"))

    # Compute workload_minutes from the course carga_horaria (hours → minutes)
    workload_minutes = int(course.carga_horaria * 60) if course.carga_horaria else None

    # For NORMATIVE_MINIMUM courses, workload_minutes must equal normative_minimum_minutes
    normative_minimum_minutes = reg.get("normative_minimum_minutes")
    if reg["workload_source"] == WorkloadSource.NORMATIVE_MINIMUM and normative_minimum_minutes:
        workload_minutes = normative_minimum_minutes

    # Determine delivery_mode — use regulatory override if set, else course modality
    delivery_mode = reg.get("modality") or course.modality.value

    # Determine status — REVIEW_REQUIRED for NR-18-F, else DRAFT
    status = reg.get("status", ComplianceStatus.DRAFT)

    # Prerequisites
    prerequisites = reg.get("prerequisite")
    prerequisite_text = f"Requer conclusão do curso {prerequisites}" if prerequisites else None

    # Validity period
    validity_months = reg.get("validity_months")

    # Practical component
    requires_practical = reg.get("requires_practical_component", False)

    # Check if profile already exists
    result = await db.execute(
        select(CourseComplianceProfile).where(
            CourseComplianceProfile.tenant_id == tenant_id,
            CourseComplianceProfile.course_id == course.id,
        )
    )
    profile = result.scalar_one_or_none()

    if profile is None:
        # Create new profile with regulatory matrix values
        profile = CourseComplianceProfile(
            tenant_id=tenant_id,
            course_id=course.id,
            regulatory_standard=standard,
            regulatory_version=version,
            delivery_mode=delivery_mode,
            workload_source=reg["workload_source"],
            workload_minutes=workload_minutes,
            normative_minimum_minutes=normative_minimum_minutes,
            requires_practical_component=requires_practical,
            requires_final_assessment=True,
            validity_period_months=validity_months,
            prerequisites=prerequisite_text,
            certificate_required_fields=[],
            status=status,
        )
        db.add(profile)
    else:
        # Update ONLY the fields managed by the regulatory matrix.
        # Never overwrite manually-configured fields.
        profile.regulatory_standard = standard
        profile.regulatory_version = version
        profile.delivery_mode = delivery_mode
        profile.workload_source = reg["workload_source"]
        profile.workload_minutes = workload_minutes
        profile.normative_minimum_minutes = normative_minimum_minutes
        profile.requires_practical_component = requires_practical
        if validity_months is not None:
            profile.validity_period_months = validity_months
        if prerequisite_text is not None:
            profile.prerequisites = prerequisite_text
        # Only set status to REVIEW_REQUIRED if it was DRAFT (don't downgrade
        # a COMPLIANCE_READY profile — that requires manual review).
        if status == ComplianceStatus.REVIEW_REQUIRED and profile.status == ComplianceStatus.DRAFT:
            profile.status = status

    return profile


async def reconcile_regulatory_compliance(
    db: AsyncSession,
    tenant_id: UUID,
    manifest: dict,
    dry_run: bool = True,
) -> dict:
    """Reconcile all 14 priority courses with their regulatory profiles.

    Calls upsert_regulatory_compliance_profile for each course that has
    an entry in REGULATORY_WORKLOAD.
    """
    report = {"CREATED_PROFILE": [], "UPDATED_PROFILE": [], "SKIPPED": []}

    # Load all existing courses for this tenant
    result = await db.execute(select(Course).where(Course.tenant_id == tenant_id))
    existing_courses = {c.code: c for c in result.scalars().all()}

    for entry in manifest["courses"]:
        code = entry["code"]
        if code not in REGULATORY_WORKLOAD:
            continue
        course = existing_courses.get(code)
        if not course:
            report["SKIPPED"].append({"code": code, "reason": "course not found"})
            continue

        if not dry_run:
            profile = await upsert_regulatory_compliance_profile(db, tenant_id, course, entry)
            if profile:
                report["CREATED_PROFILE"].append({"code": code})
            else:
                report["SKIPPED"].append({"code": code, "reason": "no regulatory entry"})
        else:
            report["CREATED_PROFILE"].append({"code": code, "dry_run": True})

    return report


def _to_text(value) -> str | None:
    """Convert a value to a string suitable for Text columns, or None."""
    if value is None or value == "REVIEW_REQUIRED":
        return None
    if isinstance(value, list):
        return "; ".join(str(v) for v in value) if value else None
    return str(value)


def _build_profile_data(content: dict, entry: dict, manifest_hash: str, manifest_version: str) -> dict:
    """Build CourseContentProfile fields from manifest content.

    Academic content (syllabus, key_topics, risks, prevention) extracted
    from the source apostila is NOT auto-promoted to SOURCE_CONFIRMED.
    SOURCE_CONFIRMED requires an explicit approval signal from the
    manifest (``content_approval`` block) or an external confirmation
    action. Without that signal, the profile stays INFERRED.

    Workload, modality, practice, recycling, technical responsible, and
    professional qualification are NOT promoted here — they have their
    own regulatory compliance cycle.
    """
    # Default to INFERRED — never auto-confirm just because content exists.
    review_status = ReviewStatus.INFERRED
    approval_source = None
    approved_at = None

    # Explicit approval signal from the manifest. The owner may record
    # that the academic content was externally confirmed.
    approval = entry.get("content_approval") or {}
    if approval.get("confirmed") is True:
        review_status = ReviewStatus.SOURCE_CONFIRMED
        approval_source = approval.get("source", OWNER_EXTERNAL_CONFIRMATION)
        approved_at = approval.get("confirmed_at")

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
        "review_status": review_status,
        "review_required_fields": entry.get("review_required_fields", []),
        "manifest_hash": manifest_hash,
        "manifest_version": manifest_version,
        "approval_source": approval_source,
        "approved_at": approved_at,
        # approved_by stays NULL — no in-database user represents the
        # external owner confirmation. approval_source records the trail.
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

    manifest_bytes = MANIFEST_PATH.read_bytes()
    manifest_hash = compute_manifest_hash(manifest_bytes)
    manifest_version = compute_manifest_version(MANIFEST_PATH)
    manifest = json.loads(manifest_bytes)
    print(f"Loaded manifest: {len(manifest['courses'])} courses, {len(manifest.get('deactivate_codes', []))} to deactivate")
    print(f"Manifest hash: {manifest_hash}")
    print(f"Manifest version: {manifest_version}")

    async with AsyncSessionLocal() as db:
        tenant_id = await get_wr_tenant_id(db)
        if not tenant_id:
            print("ERROR: WR tenant not found")
            sys.exit(1)
        print(f"WR tenant ID: {tenant_id}")

        report = await import_catalog(
            db, tenant_id, manifest, dry_run=dry_run,
            manifest_hash=manifest_hash, manifest_version=manifest_version,
        )

        # Reconcile regulatory compliance profiles for the 14 priority courses
        reg_report = await reconcile_regulatory_compliance(db, tenant_id, manifest, dry_run=dry_run)
        report.update(reg_report)

        if args.upload_materials:
            mat_report = await import_materials(db, tenant_id, manifest, dry_run=dry_run, upload=True)
            report.update(mat_report)

        print_report(report, dry_run)


if __name__ == "__main__":
    asyncio.run(main())
