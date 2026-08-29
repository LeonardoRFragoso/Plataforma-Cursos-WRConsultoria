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
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.compliance import ComplianceStatus, CourseComplianceProfile, WorkloadSource
from app.models.course import Course, CourseModality
from app.models.course_content_profile import CourseContentProfile, ReviewStatus
from app.models.course_material import CourseMaterial
from app.models.tenant import Tenant

# Demo markers reused for demo_classification. These MUST stay in sync with
# app/scripts/create_demo_certificate.py and app/services/certificate_service.py.
DEMO_CERTIFICATE_PREFIX = "DEMO-"
DEMO_EMAIL_DOMAIN = "demo.local"
DEMO_CLASS_LOCATION = "DEMO-CERT-EAD"

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


# ---------------------------------------------------------------------------
# Compliance blocker codes stored in CourseComplianceProfile.compliance_blockers
# ---------------------------------------------------------------------------
BLOCKER_COURSE_FIELD_HISTORY_CONFLICT = "COURSE_FIELD_HISTORY_CONFLICT"
BLOCKER_NR18_VARIANT_CONFIRMATION_REQUIRED = "NR18_VARIANT_CONFIRMATION_REQUIRED"
BLOCKER_SOURCE_REGULATORY_RECONCILIATION = "REGULATORY_RECONCILIATION"


@dataclass
class ComplianceProfilePlan:
    """Pure plan for a single course's compliance profile reconciliation.

    Computed by ``plan_compliance_profile()`` and consumed identically by
    dry-run (report only) and apply (mutate DB). This guarantees dry-run /
    apply parity — there is exactly one implementation of the rules.
    """

    action: str  # CREATED, UPDATED, NO_CHANGE, SKIPPED
    code: str
    current_state: dict | None = None
    target_state: dict = field(default_factory=dict)
    changes: list[dict] = field(default_factory=list)
    target_status: str = ComplianceStatus.DRAFT
    target_blockers: list[dict] = field(default_factory=list)
    blocker_changes: list[dict] = field(default_factory=list)


def _build_blocker(code: str, details: dict | None = None) -> dict:
    """Build a compliance blocker dict in the canonical format."""
    return {
        "code": code,
        "source": BLOCKER_SOURCE_REGULATORY_RECONCILIATION,
        "details": details or {},
    }


def _merge_blockers(
    existing: list[dict],
    to_add: list[dict],
    to_remove_codes: set[str],
) -> tuple[list[dict], list[dict]]:
    """Merge compliance blockers idempotently.

    - ``to_add``: blockers that should be present (deduplicated by code).
    - ``to_remove_codes``: blocker codes that should be removed (resolved).
      Only codes managed by this reconciler are removed — external blockers
      (codes not in to_remove_codes) are always preserved.

    Returns (merged_blockers, blocker_changes) where blocker_changes is a
    list of ``{"action": "added"|"removed", "code": ...}`` for reporting.
    """
    by_code: dict[str, dict] = {}
    for b in existing:
        # Defensive: handle malformed blockers (non-dict or missing code)
        if isinstance(b, dict) and "code" in b:
            by_code[b["code"]] = b
        else:
            # Preserve malformed/external blockers with a synthetic key
            # so they are not lost. They will be preserved but not managed.
            by_code[f"__malformed_{id(b)}"] = b

    changes: list[dict] = []

    # Remove resolved blockers (only codes explicitly in to_remove_codes)
    for code in to_remove_codes:
        if code in by_code:
            del by_code[code]
            changes.append({"action": "removed", "code": code})

    # Add new blockers (idempotent — no duplication)
    for blocker in to_add:
        if blocker["code"] not in by_code:
            by_code[blocker["code"]] = blocker
            changes.append({"action": "added", "code": blocker["code"]})

    return list(by_code.values()), changes


def plan_compliance_profile(
    course: Course,
    entry: dict,
    existing: CourseComplianceProfile | None,
    force_review_required: bool = False,
    review_blocker_fields: list[str] | None = None,
) -> ComplianceProfilePlan:
    """Pure planner for compliance profile reconciliation.

    Computes the target state for a course's compliance profile based on
    REGULATORY_WORKLOAD, the existing profile (if any), and any history
    conflict (force_review_required). Returns a plan that can be applied
    identically by dry-run and apply.

    FIELD OWNERSHIP:
    - MATRIX-OWNED (reconciler controls): regulatory_standard, regulatory_version,
      delivery_mode, workload_source, workload_minutes, normative_minimum_minutes,
      requires_practical_component, requires_final_assessment.
    - MATRIX-OWNED CONDITIONAL: validity_period_months (only when matrix defines
      validity_months explicitly), prerequisites (only when matrix defines
      prerequisite explicitly), compliance_blockers (only for codes managed
      by this reconciler).
    - MANUAL-OWNED / PRESERVE: certificate_required_fields, technical_responsible_id,
      pedagogical_project_version_id, minimum_score, last_compliance_review_at,
      next_compliance_review_at. Never reported as changes, never overwritten.

    Rules:
    - ``force_review_required=True`` → target_status=REVIEW_REQUIRED,
      COURSE_FIELD_HISTORY_CONFLICT blocker added.
    - NR-18 variant confirmation: blocker added when matrix indicates
      REVIEW_REQUIRED (status or workload_source), NOT hardcoded by code.
      After future matrix update (status != REVIEW_REQUIRED), blocker is
      removed but status stays REVIEW_REQUIRED (no auto-promote).
    - ARCHIVED profiles are never reactivated.
    - REGULATORY REVALIDATION: if existing.status == COMPLIANCE_READY and
      at least one MATERIAL compliance field changes (or a new blocker is
      added), target_status is downgraded to REVIEW_REQUIRED. A previously
      approved profile cannot silently stay approved when its regulatory
      parameters change.
    - No auto-promote: once REVIEW_REQUIRED, status stays REVIEW_REQUIRED
      even if the blocker is resolved or all material fields match again.
    - Blockers are deduplicated by code (idempotent).
    - External blockers (not managed by this reconciler) are always preserved.
    - Resolved blockers are removed from the list, but status remains REVIEW_REQUIRED.
    """
    code = entry.get("code", "")
    reg = REGULATORY_WORKLOAD.get(code)
    if reg is None:
        return ComplianceProfilePlan(action="SKIPPED", code=code)

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

    # Determine base status from matrix
    matrix_status = reg.get("status", ComplianceStatus.DRAFT)

    # Determine if NR-18 variant confirmation is needed — based on matrix
    # status/workload_source, NOT hardcoded by course code. This allows
    # future matrix updates to remove the blocker after human confirmation.
    nr18_variant_needs_review = (
        matrix_status == ComplianceStatus.REVIEW_REQUIRED
        or reg["workload_source"] == WorkloadSource.REVIEW_REQUIRED
    ) and code.startswith("NR-18")

    # Determine target blockers
    blockers_to_add: list[dict] = []
    blockers_to_remove: set[str] = set()

    # NR-18 variant confirmation blocker — only when matrix indicates review needed
    if nr18_variant_needs_review:
        blockers_to_add.append(_build_blocker(BLOCKER_NR18_VARIANT_CONFIRMATION_REQUIRED))
    else:
        # Matrix no longer requires NR-18 variant review → remove blocker
        blockers_to_remove.add(BLOCKER_NR18_VARIANT_CONFIRMATION_REQUIRED)

    # History conflict blocker
    if force_review_required:
        blockers_to_add.append(
            _build_blocker(
                BLOCKER_COURSE_FIELD_HISTORY_CONFLICT,
                {"fields": review_blocker_fields or ["modality"]},
            )
        )
    else:
        # No history conflict → remove the blocker if it was previously present
        blockers_to_remove.add(BLOCKER_COURSE_FIELD_HISTORY_CONFLICT)

    # Validity period — matrix-owned ONLY when matrix defines validity_months explicitly
    matrix_validity_months = reg.get("validity_months")
    if matrix_validity_months is not None:
        target_validity = matrix_validity_months
    elif existing is not None:
        # Matrix doesn't define validity → preserve existing value (manual-owned)
        target_validity = existing.validity_period_months
    else:
        # New profile, matrix doesn't define → None
        target_validity = None

    # Practical component
    requires_practical = reg.get("requires_practical_component", False)

    # Prerequisites — matrix-owned ONLY when matrix defines prerequisite explicitly
    matrix_prerequisite = reg.get("prerequisite")
    if matrix_prerequisite is not None:
        target_prerequisites = f"Requer conclusão do curso {matrix_prerequisite}"
    elif existing is not None:
        # Matrix doesn't define prerequisite → preserve existing (manual-owned)
        target_prerequisites = existing.prerequisites
    else:
        # New profile, matrix doesn't define → None
        target_prerequisites = None

    # certificate_required_fields — MANUAL-OWNED, always preserve existing
    target_cert_fields = list(existing.certificate_required_fields) if existing and existing.certificate_required_fields else []

    # Compute target blockers by merging with existing
    existing_blockers = list(existing.compliance_blockers) if existing and existing.compliance_blockers else []
    merged_blockers, blocker_changes = _merge_blockers(existing_blockers, blockers_to_add, blockers_to_remove)

    # -----------------------------------------------------------------------
    # MATERIAL COMPLIANCE FIELDS — used for regulatory revalidation.
    # These are the fields whose change invalidates a previous COMPLIANCE_READY
    # approval. MANUAL-OWNED fields are NOT included (they have their own
    # lifecycles and don't invalidate regulatory approval).
    # -----------------------------------------------------------------------
    MATERIAL_FIELDS = [
        "regulatory_standard",
        "regulatory_version",
        "delivery_mode",
        "workload_source",
        "workload_minutes",
        "normative_minimum_minutes",
        "requires_practical_component",
        "requires_final_assessment",
        "validity_period_months",
        "prerequisites",
        "compliance_blockers",
    ]

    # Build target state (without status — status is computed after material
    # changes are detected to avoid an artificial cycle).
    target_state_no_status = {
        "regulatory_standard": standard,
        "regulatory_version": version,
        "delivery_mode": delivery_mode,
        "workload_source": reg["workload_source"],
        "workload_minutes": workload_minutes,
        "normative_minimum_minutes": normative_minimum_minutes,
        "requires_practical_component": requires_practical,
        "requires_final_assessment": True,
        "validity_period_months": target_validity,
        "prerequisites": target_prerequisites,
        "certificate_required_fields": target_cert_fields,
        "compliance_blockers": merged_blockers,
    }

    # Compute material changes BEFORE deciding status (avoids artificial cycle
    # where status change itself would be counted as a material change).
    material_changes: list[dict] = []
    if existing is not None:
        existing_values = {
            "regulatory_standard": existing.regulatory_standard,
            "regulatory_version": existing.regulatory_version,
            "delivery_mode": existing.delivery_mode,
            "workload_source": existing.workload_source,
            "workload_minutes": existing.workload_minutes,
            "normative_minimum_minutes": existing.normative_minimum_minutes,
            "requires_practical_component": existing.requires_practical_component,
            "requires_final_assessment": existing.requires_final_assessment,
            "validity_period_months": existing.validity_period_months,
            "prerequisites": existing.prerequisites,
            "compliance_blockers": list(existing.compliance_blockers) if existing.compliance_blockers else [],
        }
        for field_name in MATERIAL_FIELDS:
            target_val = target_state_no_status.get(field_name)
            current_val = existing_values.get(field_name)
            if current_val != target_val:
                material_changes.append({"field": field_name, "before": current_val, "after": target_val})

    # Check if a new blocker was added (also invalidates COMPLIANCE_READY)
    new_blocker_added = any(c["action"] == "added" for c in blocker_changes)

    # Determine target status — computed AFTER material_changes to avoid
    # the artificial cycle where status change would be counted as material.
    if existing is None:
        # New profile
        target_status = (
            ComplianceStatus.REVIEW_REQUIRED
            if (force_review_required or nr18_variant_needs_review or matrix_status == ComplianceStatus.REVIEW_REQUIRED)
            else matrix_status
        )
    elif existing.status == ComplianceStatus.ARCHIVED:
        # ARCHIVED: never reactivate. Keep status, report manual review needed.
        target_status = ComplianceStatus.ARCHIVED
    elif force_review_required or nr18_variant_needs_review or matrix_status == ComplianceStatus.REVIEW_REQUIRED:
        # Force REVIEW_REQUIRED from DRAFT, IN_REVIEW, or COMPLIANCE_READY.
        # Never auto-promote back — once REVIEW_REQUIRED, stays REVIEW_REQUIRED
        # even after blocker resolution.
        target_status = ComplianceStatus.REVIEW_REQUIRED
    elif existing.status == ComplianceStatus.COMPLIANCE_READY and (material_changes or new_blocker_added):
        # REGULATORY REVALIDATION: a previously approved profile cannot stay
        # COMPLIANCE_READY when material compliance fields change or a new
        # blocker is added. Downgrade to REVIEW_REQUIRED for human re-approval.
        target_status = ComplianceStatus.REVIEW_REQUIRED
    else:
        # No force, no NR-18 review, matrix is not REVIEW_REQUIRED, and either:
        # - status is DRAFT/IN_REVIEW/REVIEW_REQUIRED (preserve, no auto-promote), or
        # - status is COMPLIANCE_READY with no material changes (stay approved).
        target_status = existing.status

    # Build final target state with status
    target_state = dict(target_state_no_status)
    target_state["status"] = target_status

    if existing is None:
        # New profile — all fields are "changes"
        current_state = None
        changes = [{"field": k, "after": v} for k, v in target_state.items()]
        action = "CREATED"
    else:
        current_state = {
            "regulatory_standard": existing.regulatory_standard,
            "regulatory_version": existing.regulatory_version,
            "delivery_mode": existing.delivery_mode,
            "workload_source": existing.workload_source,
            "workload_minutes": existing.workload_minutes,
            "normative_minimum_minutes": existing.normative_minimum_minutes,
            "requires_practical_component": existing.requires_practical_component,
            "requires_final_assessment": existing.requires_final_assessment,
            "validity_period_months": existing.validity_period_months,
            "prerequisites": existing.prerequisites,
            "certificate_required_fields": existing.certificate_required_fields,
            "status": existing.status,
            "compliance_blockers": list(existing.compliance_blockers) if existing.compliance_blockers else [],
        }

        changes: list[dict] = []
        for k, target_val in target_state.items():
            current_val = current_state.get(k)
            # Compare — handle list/dict equality
            if current_val != target_val:
                changes.append({"field": k, "before": current_val, "after": target_val})

        action = "UPDATED" if changes else "NO_CHANGE"

    return ComplianceProfilePlan(
        action=action,
        code=code,
        current_state=current_state,
        target_state=target_state,
        changes=changes,
        target_status=target_status,
        target_blockers=merged_blockers,
        blocker_changes=blocker_changes,
    )


def _apply_plan_to_profile(
    plan: ComplianceProfilePlan,
    tenant_id: UUID,
    course_id: UUID,
    existing: CourseComplianceProfile | None,
) -> CourseComplianceProfile:
    """Apply a plan to a profile object (mutates existing or creates new).

    This is the ONLY place that mutates profile fields. Called by apply mode.

    FIELD OWNERSHIP:
    - MATRIX-OWNED fields are set from plan.target_state.
    - MANUAL-OWNED fields (certificate_required_fields, technical_responsible_id,
      pedagogical_project_version_id, minimum_score, last_compliance_review_at,
      next_compliance_review_at) are NEVER overwritten on existing profiles.
    - For new profiles, manual-owned fields start at their defaults (empty/null).
    - validity_period_months and prerequisites: the planner already computed
      the correct target (matrix value if defined, else existing value), so
      we always set them from target_state. This is safe because the planner
      preserves existing values when the matrix doesn't define them.
    """
    if existing is None:
        profile = CourseComplianceProfile(
            tenant_id=tenant_id,
            course_id=course_id,
            regulatory_standard=plan.target_state["regulatory_standard"],
            regulatory_version=plan.target_state["regulatory_version"],
            delivery_mode=plan.target_state["delivery_mode"],
            workload_source=plan.target_state["workload_source"],
            workload_minutes=plan.target_state["workload_minutes"],
            normative_minimum_minutes=plan.target_state["normative_minimum_minutes"],
            requires_practical_component=plan.target_state["requires_practical_component"],
            requires_final_assessment=plan.target_state["requires_final_assessment"],
            validity_period_months=plan.target_state["validity_period_months"],
            prerequisites=plan.target_state["prerequisites"],
            certificate_required_fields=plan.target_state["certificate_required_fields"],
            compliance_blockers=plan.target_blockers,
            status=plan.target_status,
        )
        return profile

    # Update existing profile — only MATRIX-OWNED fields.
    # MANUAL-OWNED fields are NEVER touched here.
    existing.regulatory_standard = plan.target_state["regulatory_standard"]
    existing.regulatory_version = plan.target_state["regulatory_version"]
    existing.delivery_mode = plan.target_state["delivery_mode"]
    existing.workload_source = plan.target_state["workload_source"]
    existing.workload_minutes = plan.target_state["workload_minutes"]
    existing.normative_minimum_minutes = plan.target_state["normative_minimum_minutes"]
    existing.requires_practical_component = plan.target_state["requires_practical_component"]
    existing.requires_final_assessment = plan.target_state["requires_final_assessment"]
    # validity_period_months: planner already set target = existing when matrix
    # doesn't define it, so this is safe (no clobbering of manual values).
    existing.validity_period_months = plan.target_state["validity_period_months"]
    # prerequisites: planner already set target = existing when matrix doesn't
    # define it, so this is safe (no clobbering of manual values).
    existing.prerequisites = plan.target_state["prerequisites"]
    existing.compliance_blockers = plan.target_blockers
    # certificate_required_fields: MANUAL-OWNED — NEVER overwritten.

    # Status: only downgrade to REVIEW_REQUIRED, never auto-promote
    if plan.target_status == ComplianceStatus.REVIEW_REQUIRED and existing.status != ComplianceStatus.ARCHIVED:
        existing.status = ComplianceStatus.REVIEW_REQUIRED

    return existing


async def upsert_regulatory_compliance_profile(
    db: AsyncSession,
    tenant_id: UUID,
    course: Course,
    entry: dict,
    force_review_required: bool = False,
    review_blocker_fields: list[str] | None = None,
) -> tuple[CourseComplianceProfile | None, str, ComplianceProfilePlan | None]:
    """Idempotently upsert a CourseComplianceProfile from REGULATORY_WORKLOAD.

    Uses ``plan_compliance_profile()`` to compute the plan, then applies it
    (in apply mode). Returns (profile, action, plan).

    When ``force_review_required`` is True (Course field change blocked by
    historical records), the profile status is set to REVIEW_REQUIRED
    regardless of current status (DRAFT, IN_REVIEW, or COMPLIANCE_READY).
    ARCHIVED profiles are never reactivated. The blocker is stored in
    ``compliance_blockers`` (NOT prerequisites).

    Returns (profile, action, plan) where action is "CREATED", "UPDATED",
    or "NO_CHANGE". Returns (None, "SKIPPED", plan) if the course code has
    no regulatory matrix entry.
    """
    # Check if profile already exists
    result = await db.execute(
        select(CourseComplianceProfile).where(
            CourseComplianceProfile.tenant_id == tenant_id,
            CourseComplianceProfile.course_id == course.id,
        )
    )
    existing = result.scalar_one_or_none()

    plan = plan_compliance_profile(
        course=course,
        entry=entry,
        existing=existing,
        force_review_required=force_review_required,
        review_blocker_fields=review_blocker_fields,
    )

    if plan.action == "SKIPPED":
        return None, "SKIPPED", plan

    # Apply the plan (mutate DB)
    profile = _apply_plan_to_profile(plan, tenant_id, course.id, existing)
    if existing is None:
        db.add(profile)

    return profile, plan.action, plan


def _classify_enrollment_demo(
    cert_nums: list[str],
    user_email: str | None,
    class_location: str | None,
) -> tuple[str, list[str]]:
    """Classify an enrollment as demo, non-demo, or unknown.

    Uses known demo markers (certificate prefix, email domain, class location)
    as positive evidence. Returns (classification, evidence_codes).

    Classification:
    - CONFIRMED_DEMO: at least one positive demo evidence marker found.
    - UNKNOWN: no positive demo evidence. NEVER assume NON_DEMO from absence
      of evidence (fail-closed).

    CONFIRMED_NON_DEMO is only returned when there is positive evidence of
    operational/production origin. Since no reliable criteria for that exist
    in the current data model, UNKNOWN is used instead.

    No PII is returned — only classification and evidence codes.
    """
    evidence_codes: list[str] = []

    # Evidence: certificate number prefixed with DEMO-
    if any(c.startswith(DEMO_CERTIFICATE_PREFIX) for c in cert_nums):
        evidence_codes.append("DEMO_CERTIFICATE_PREFIX")

    # Evidence: user email domain is a known demo domain.
    # Exact match on "demo.local" OR subdomain ending with ".demo.local".
    # Normalized to lowercase to be case-insensitive.
    # This prevents false positives like "notdemo.local".
    if user_email:
        domain = user_email.split("@")[-1].lower()
        if domain == DEMO_EMAIL_DOMAIN or domain.endswith(f".{DEMO_EMAIL_DOMAIN}"):
            evidence_codes.append("DEMO_USER_EMAIL_DOMAIN")

    # Evidence: class location matches the known demo class marker
    if class_location == DEMO_CLASS_LOCATION:
        evidence_codes.append("DEMO_CLASS_LOCATION")

    if evidence_codes:
        return "CONFIRMED_DEMO", evidence_codes
    # Fail-closed: absence of demo evidence does NOT confirm NON_DEMO.
    return "UNKNOWN", []


async def _course_has_historical_records(db: AsyncSession, tenant_id: UUID, course_id: UUID) -> dict:
    """Check if a course has enrollments or certificates that could be
    retroactively reinterpreted by a Course field change.

    Returns a dict with counts and per-enrollment detail (no CPF, no email,
    no full name — only demo_classification and evidence_codes):
        {"enrollments": N, "certificates": N, "details": [...]}
    Used by reconcile_regulatory_course_fields to decide whether a Course
    field change is safe or must be flagged MANUAL_REVIEW_REQUIRED.
    """
    from app.models.certificate import Certificate
    from app.models.class_model import Class
    from app.models.enrollment import Enrollment
    from app.models.student import Student
    from app.models.user import User

    # Load enrollments for classes of this course (with class + student + user info)
    enr_result = await db.execute(
        select(Enrollment, Class, Student, User)
        .join(Class, Class.id == Enrollment.class_id)
        .join(Student, Student.id == Enrollment.student_id)
        .join(User, User.id == Student.user_id)
        .where(
            Enrollment.tenant_id == tenant_id,
            Class.course_id == course_id,
        )
    )
    rows = enr_result.all()
    enrollment_ids = [row[0].id for row in rows]

    # Count certificates per enrollment
    cert_counts: dict = {}
    if enrollment_ids:
        cert_result = await db.execute(
            select(Certificate.enrollment_id, Certificate.certificate_number)
            .where(
                Certificate.tenant_id == tenant_id,
                Certificate.enrollment_id.in_(enrollment_ids),
            )
        )
        for eid, cert_num in cert_result.all():
            cert_counts.setdefault(eid, []).append(cert_num)

    details = []
    for enrollment, cls, _student, user in rows:
        cert_nums = cert_counts.get(enrollment.id, [])
        demo_classification, evidence_codes = _classify_enrollment_demo(
            cert_nums=cert_nums,
            user_email=user.email if user else None,
            class_location=cls.location if cls else None,
        )
        details.append({
            "enrollment_id": str(enrollment.id),
            "status": enrollment.status.value if hasattr(enrollment.status, "value") else str(enrollment.status),
            "class_id": str(cls.id),
            "certificate_count": len(cert_nums),
            "demo_classification": demo_classification,
            "evidence_codes": evidence_codes,
        })

    return {
        "enrollments": len(enrollment_ids),
        "certificates": sum(len(v) for v in cert_counts.values()),
        "details": details,
    }


async def reconcile_regulatory_course_fields(
    db: AsyncSession,
    tenant_id: UUID,
    manifest: dict,
    dry_run: bool = True,
) -> dict:
    """Safely align Course.carga_horaria and Course.modality with REGULATORY_WORKLOAD.

    SAFETY GUARANTEES:
    - Only operates on course codes present in REGULATORY_WORKLOAD (the 14
      priority courses). Other courses are never touched.
    - Only operates on the given tenant_id.
    - carga_horaria is aligned ONLY when workload_source == NORMATIVE_MINIMUM
      and normative_minimum_minutes is defined. EMPLOYER_DEFINED,
      PLH_DEFINED, and REVIEW_REQUIRED workloads are never overwritten.
    - modality is aligned ONLY when REGULATORY_WORKLOAD[code]["modality"] is
      not None. A None modality (NR-18-F) means "do not override".
    - NR-18-F: neither carga_horaria nor modality is altered (workload_source
      is REVIEW_REQUIRED, modality is None).
    - Historical safety: if the course has existing enrollments or
      certificates, the Course field change is flagged
      MANUAL_REVIEW_REQUIRED and NOT applied silently. Issued certificates
      are never retroactively recalculated.
    - Idempotent: re-running produces 0 course updates.
    - Transactional: the caller is responsible for committing.

    Report format (per field change):
        {
            "code": "NR-33-SUP",
            "field": "carga_horaria",
            "before": 16,
            "after": 40,
            "source": "NORMATIVE_MINIMUM",
            "reason": "...",
            "action": "UPDATE",
        }
    """
    report: dict = {
        "COURSE_FIELD_UPDATES": [],
        "MANUAL_REVIEW_REQUIRED": [],
        "COURSE_FIELD_SKIPPED": [],
        "COURSE_FIELD_NO_CHANGE": [],
    }
    # Codes that have history conflicts — passed to reconcile_regulatory_compliance
    # so the profile is created as REVIEW_REQUIRED with a compliance blocker.
    # Maps code → list of conflicting field names (for blocker details).
    manual_review_codes: dict[str, list[str]] = {}

    # Load all existing courses for this tenant
    result = await db.execute(select(Course).where(Course.tenant_id == tenant_id))
    existing_courses = {c.code: c for c in result.scalars().all()}

    for entry in manifest["courses"]:
        code = entry["code"]
        if code not in REGULATORY_WORKLOAD:
            continue
        course = existing_courses.get(code)
        if not course:
            report["COURSE_FIELD_SKIPPED"].append({"code": code, "reason": "course not found"})
            continue

        reg = REGULATORY_WORKLOAD[code]
        workload_source = reg["workload_source"]
        normative_minimum_minutes = reg.get("normative_minimum_minutes")
        reg_modality = reg.get("modality")

        # Determine planned changes
        planned_changes: list[dict] = []

        # carga_horaria: only for NORMATIVE_MINIMUM with a defined minimum
        if workload_source == WorkloadSource.NORMATIVE_MINIMUM and normative_minimum_minutes:
            target_ch = normative_minimum_minutes // 60
            if course.carga_horaria != target_ch:
                planned_changes.append({
                    "field": "carga_horaria",
                    "before": course.carga_horaria,
                    "after": target_ch,
                    "source": "NORMATIVE_MINIMUM",
                    "reason": f"Matrix requires {target_ch}h normative minimum (was {course.carga_horaria}h)",
                })

        # modality: only when matrix explicitly defines an override (not None)
        if reg_modality is not None:
            target_modality = CourseModality(reg_modality)
            if course.modality != target_modality:
                planned_changes.append({
                    "field": "modality",
                    "before": course.modality.value,
                    "after": reg_modality,
                    "source": "REGULATORY_WORKLOAD",
                    "reason": f"Matrix requires {reg_modality} modality (was {course.modality.value})",
                })

        if not planned_changes:
            report["COURSE_FIELD_NO_CHANGE"].append({"code": code})
            continue

        # Historical safety check — if the course has enrollments/certificates,
        # do NOT modify Course fields silently. Flag for manual review.
        history = await _course_has_historical_records(db, tenant_id, course.id)
        if history["enrollments"] > 0 or history["certificates"] > 0:
            conflict_fields = [c["field"] for c in planned_changes]
            manual_review_codes[code] = conflict_fields
            report["MANUAL_REVIEW_REQUIRED"].append({
                "code": code,
                "reason": (
                    f"Course has {history['enrollments']} enrollment(s) and "
                    f"{history['certificates']} certificate(s). Course field "
                    "changes require manual review to preserve historical "
                    "snapshot integrity."
                ),
                "planned_changes": planned_changes,
                "historical_records": {
                    "enrollments": history["enrollments"],
                    "certificates": history["certificates"],
                    "details": history["details"],
                },
            })
            continue

        # Apply changes
        for change in planned_changes:
            change_entry = {
                "code": code,
                "field": change["field"],
                "before": change["before"],
                "after": change["after"],
                "source": change["source"],
                "reason": change["reason"],
                "action": "UPDATE",
            }
            report["COURSE_FIELD_UPDATES"].append(change_entry)
            if not dry_run:
                if change["field"] == "carga_horaria":
                    course.carga_horaria = change["after"]
                elif change["field"] == "modality":
                    course.modality = CourseModality(change["after"])

    report["_manual_review_codes"] = manual_review_codes
    return report


async def reconcile_regulatory_compliance(
    db: AsyncSession,
    tenant_id: UUID,
    manifest: dict,
    dry_run: bool = True,
    manual_review_codes: dict[str, list[str]] | set[str] | None = None,
) -> dict:
    """Reconcile all 14 priority courses with their regulatory profiles.

    Uses ``plan_compliance_profile()`` to compute the plan for each course,
    ensuring dry-run / apply parity. In dry-run mode the plan is reported
    but NOT applied. In apply mode the plan is applied to the DB.

    ``manual_review_codes``: codes whose Course field changes were blocked
    by historical records. Can be a dict mapping code → conflicting fields,
    or a set of codes (fields default to ["modality"]). For these, the
    profile is created/updated with status=REVIEW_REQUIRED and a
    COURSE_FIELD_HISTORY_CONFLICT compliance blocker, so the readiness gate
    blocks official certificate issuance until the divergence is resolved.

    Report uses namespaced keys to avoid collisions with field_report:
    - PROFILE_CREATED
    - PROFILE_UPDATED (includes ``changes`` list)
    - PROFILE_NO_CHANGE
    - PROFILE_SKIPPED
    """
    report: dict = {
        "PROFILE_CREATED": [],
        "PROFILE_UPDATED": [],
        "PROFILE_NO_CHANGE": [],
        "PROFILE_SKIPPED": [],
    }
    # Normalize manual_review_codes to dict[str, list[str]]
    review_fields_map: dict[str, list[str]] = {}
    if manual_review_codes is not None:
        if isinstance(manual_review_codes, dict):
            review_fields_map = manual_review_codes
        else:
            # Backwards compat: set of codes → default fields
            review_fields_map = {code: ["modality"] for code in manual_review_codes}

    # Load all existing courses for this tenant
    result = await db.execute(select(Course).where(Course.tenant_id == tenant_id))
    existing_courses = {c.code: c for c in result.scalars().all()}

    for entry in manifest["courses"]:
        code = entry["code"]
        if code not in REGULATORY_WORKLOAD:
            continue
        course = existing_courses.get(code)
        if not course:
            report["PROFILE_SKIPPED"].append({"code": code, "reason": "course not found"})
            continue

        force_review = code in review_fields_map
        review_blocker_fields = review_fields_map.get(code, ["modality"])

        # Load existing profile (needed for both dry-run and apply planning)
        existing_profile = (
            await db.execute(
                select(CourseComplianceProfile).where(
                    CourseComplianceProfile.tenant_id == tenant_id,
                    CourseComplianceProfile.course_id == course.id,
                )
            )
        ).scalar_one_or_none()

        # Compute plan — same logic for dry-run and apply
        plan = plan_compliance_profile(
            course=course,
            entry=entry,
            existing=existing_profile,
            force_review_required=force_review,
            review_blocker_fields=review_blocker_fields,
        )

        if plan.action == "SKIPPED":
            report["PROFILE_SKIPPED"].append({"code": code, "reason": "no regulatory entry"})
            continue

        # Build report entry
        report_entry: dict = {
            "code": code,
            "status": plan.target_status,
            "compliance_blockers": plan.target_blockers,
        }
        if plan.changes:
            report_entry["changes"] = plan.changes
        if plan.blocker_changes:
            report_entry["blocker_changes"] = plan.blocker_changes

        if plan.action == "CREATED":
            report["PROFILE_CREATED"].append(report_entry)
        elif plan.action == "UPDATED":
            report["PROFILE_UPDATED"].append(report_entry)
        elif plan.action == "NO_CHANGE":
            report["PROFILE_NO_CHANGE"].append(report_entry)

        # Apply the plan only in apply mode
        if not dry_run and plan.action in ("CREATED", "UPDATED"):
            profile = _apply_plan_to_profile(plan, tenant_id, course.id, existing_profile)
            if existing_profile is None:
                db.add(profile)

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
                   "CONFLICT", "REVIEW_REQUIRED",
                   "COURSE_FIELD_UPDATES", "MANUAL_REVIEW_REQUIRED",
                   "PROFILE_CREATED", "PROFILE_UPDATED", "PROFILE_NO_CHANGE",
                   "PROFILE_SKIPPED", "COURSE_FIELD_SKIPPED", "COURSE_FIELD_NO_CHANGE"]:
        items = report.get(action, [])
        if items:
            print(f"\n  {action} ({len(items)}):")
            for item in items[:10]:
                print(f"    - {item}")
            if len(items) > 10:
                print(f"    ... and {len(items) - 10} more")

    print(f"\n{'='*60}")
    # Count only list values, skip internal keys like _manual_review_codes
    total = sum(len(v) for v in report.values() if isinstance(v, list))
    print(f"  Total actions: {total}")
    print(f"{'='*60}\n")


async def run_regulatory_only(
    db: AsyncSession,
    tenant_id: UUID,
    manifest: dict,
    dry_run: bool,
) -> dict:
    """Execute ONLY the regulatory reconciliation flow (no catalog/materials).

    This is the explicit transaction boundary for regulatory apply. The
    caller is responsible for commit (apply) or rollback (dry-run / error).

    NOTE: The full import flow (``import_catalog``) has its own internal
    ``await db.commit()`` and is therefore NOT atomically rollbackable with
    regulatory reconciliation. ``--regulatory-only`` is the recommended
    transactionally-safe flow for regulatory reconciliation. Do NOT assume
    the full importer is atomic.
    """
    # Reconcile regulatory Course fields (carga_horaria, modality) for the
    # 14 priority courses — aligns Course table with REGULATORY_WORKLOAD.
    field_report = await reconcile_regulatory_course_fields(db, tenant_id, manifest, dry_run=dry_run)
    manual_review_codes: dict[str, list[str]] = field_report.pop("_manual_review_codes", {})

    # Reconcile regulatory compliance profiles for the 14 priority courses.
    # Pass manual_review_codes so profiles for history-blocked courses are
    # created as REVIEW_REQUIRED with a compliance blocker.
    profile_report = await reconcile_regulatory_compliance(
        db, tenant_id, manifest, dry_run=dry_run,
        manual_review_codes=manual_review_codes,
    )

    # Merge reports with namespaced keys (no .update overwrite).
    report: dict = {}
    report.update(field_report)
    report.update(profile_report)
    return report


async def main():
    parser = argparse.ArgumentParser(description="Import WR course catalog from manifest")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no changes")
    parser.add_argument("--apply", action="store_true", help="Execute changes")
    parser.add_argument("--upload-materials", action="store_true", help="Also register material metadata")
    parser.add_argument("--regulatory-only", action="store_true",
                        help="Only run regulatory reconciliation (no catalog/materials)")
    args = parser.parse_args()

    # CLI validation: exactly one of --dry-run / --apply
    if args.dry_run and args.apply:
        print("ERROR: cannot specify both --dry-run and --apply")
        sys.exit(1)
    if not args.dry_run and not args.apply:
        print("ERROR: must specify --dry-run or --apply")
        sys.exit(1)

    # --regulatory-only cannot be combined with --upload-materials
    if args.regulatory_only and args.upload_materials:
        print("ERROR: --regulatory-only cannot be combined with --upload-materials")
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
    if args.regulatory_only:
        print("Mode: REGULATORY ONLY (no catalog/materials)")

    async with AsyncSessionLocal() as db:
        tenant_id = await get_wr_tenant_id(db)
        if not tenant_id:
            print("ERROR: WR tenant not found")
            sys.exit(1)
        print(f"WR tenant ID: {tenant_id}")

        try:
            if args.regulatory_only:
                # Regulatory-only flow: explicit transaction boundary.
                # No import_catalog, no import_materials.
                report = await run_regulatory_only(db, tenant_id, manifest, dry_run=dry_run)
            else:
                # Full import flow
                report = await import_catalog(
                    db, tenant_id, manifest, dry_run=dry_run,
                    manifest_hash=manifest_hash, manifest_version=manifest_version,
                )

                # Regulatory reconciliation with manual-review propagation
                field_report = await reconcile_regulatory_course_fields(db, tenant_id, manifest, dry_run=dry_run)
                manual_review_codes = field_report.pop("_manual_review_codes", {})
                report.update(field_report)

                reg_report = await reconcile_regulatory_compliance(
                    db, tenant_id, manifest, dry_run=dry_run,
                    manual_review_codes=manual_review_codes,
                )
                report.update(reg_report)

                if args.upload_materials:
                    mat_report = await import_materials(db, tenant_id, manifest, dry_run=dry_run, upload=True)
                    report.update(mat_report)

            # Explicit transaction control: commit on apply, rollback on dry-run.
            if dry_run:
                await db.rollback()
            else:
                await db.commit()
        except Exception:
            await db.rollback()
            raise

        print_report(report, dry_run)


if __name__ == "__main__":
    asyncio.run(main())
