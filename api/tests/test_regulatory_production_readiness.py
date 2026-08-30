from __future__ import annotations

import uuid
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.api.routes import regulatory_readiness_guards
from app.models.compliance import ProfessionalBlocker
from app.models.professional_evidence import ProfessionalEvidenceType
from app.services.regulatory_rule_registry import (
    CONSERVATIVE_TWO_YEAR_BUFFER_DAYS,
    NR10_2027,
    NR10_CURRENT,
    add_calendar_years,
    nr10_source_for,
    operational_ead_access_log_retention_days,
)
from app.services.retention_policy_service import (
    build_retention_requirements,
    operational_validity_days,
    retention_policy_violations,
)
from app.core.utils import utc_now
from tests.conftest import make_valid_cpf


BASE = "/api/v1/compliance"
OPS = f"{BASE}/operations"


def test_regulatory_registry_switches_nr10_on_effective_date():
    assert nr10_source_for(date(2027, 5, 31)) == NR10_CURRENT
    assert nr10_source_for(date(2027, 6, 1)) == NR10_2027


def test_calendar_retention_handles_leap_day_and_operational_floor():
    assert add_calendar_years(date(2024, 2, 29), 2) == date(2026, 2, 28)
    assert CONSERVATIVE_TWO_YEAR_BUFFER_DAYS == 731
    assert operational_ead_access_log_retention_days(365) == 1096


def test_retention_requirements_use_safest_validity_projection():
    assert operational_validity_days(365, 12) == 372
    assert operational_validity_days(None, 12) == 372
    assert operational_validity_days(None, None) is None

    course = SimpleNamespace(code="NR-TEST", certificate_validity_days=365)
    profile = SimpleNamespace(delivery_mode="EAD", validity_period_months=12)
    requirements = build_retention_requirements([(course, profile)])
    assert requirements.minimum_training_event_retention_days == 1103
    assert requirements.unresolved_course_codes == ()
    assert retention_policy_violations(1102, requirements)
    assert retention_policy_violations(1103, requirements) == []


def test_retention_requirements_fail_closed_when_ead_validity_is_unknown():
    course = SimpleNamespace(code="NR-UNKNOWN", certificate_validity_days=None)
    profile = SimpleNamespace(delivery_mode="SEMIPRESENCIAL", validity_period_months=None)
    requirements = build_retention_requirements([(course, profile)])
    assert requirements.minimum_training_event_retention_days is None
    assert requirements.unresolved_course_codes == ("NR-UNKNOWN",)
    violations = retention_policy_violations(5000, requirements)
    assert violations == ["RETENTION_VALIDITY_UNRESOLVED: NR-UNKNOWN"]


@pytest.mark.asyncio
async def test_verified_nr10_evidence_resolves_named_professional_blockers(monkeypatch):
    async def fake_legacy(*_args, **_kwargs):
        return [
            ProfessionalBlocker.ELECTRICAL_LEGAL_QUALIFICATION_REQUIRED,
            ProfessionalBlocker.PROFICIENCY_EVIDENCE_MISSING,
        ]

    async def fake_evidence(*_args, **_kwargs):
        return {
            ProfessionalEvidenceType.LEGAL_QUALIFICATION,
            ProfessionalEvidenceType.PROFICIENCY,
        }

    monkeypatch.setattr(
        regulatory_readiness_guards.legacy_compliance,
        "_readiness_blockers",
        fake_legacy,
    )
    monkeypatch.setattr(
        regulatory_readiness_guards,
        "_verified_evidence_types",
        fake_evidence,
    )

    course = SimpleNamespace(code="NR-10-F")
    profile = SimpleNamespace(
        regulatory_standard="NR-10",
        certificate_required_fields=[
            "student_name",
            "course_name",
            "workload",
            "training_start",
            "training_end",
            "training_location",
            "instructors",
            "technical_responsible",
        ],
        technical_responsible_id=uuid.uuid4(),
    )
    blockers = await regulatory_readiness_guards.corrected_readiness_blockers(
        None,
        uuid.uuid4(),
        course,
        profile,
    )
    assert ProfessionalBlocker.ELECTRICAL_LEGAL_QUALIFICATION_REQUIRED not in blockers
    assert ProfessionalBlocker.PROFICIENCY_EVIDENCE_MISSING not in blockers


@pytest.mark.asyncio
async def test_internal_compliance_profile_is_not_forced_into_nr1_baseline(monkeypatch):
    async def fake_legacy(*_args, **_kwargs):
        return []

    monkeypatch.setattr(
        regulatory_readiness_guards.legacy_compliance,
        "_readiness_blockers",
        fake_legacy,
    )
    course = SimpleNamespace(code="INTERNAL-COMPLIANCE")
    profile = SimpleNamespace(
        regulatory_standard="TEST-NR",
        certificate_required_fields=[],
        technical_responsible_id=None,
    )
    blockers = await regulatory_readiness_guards.corrected_readiness_blockers(
        None,
        uuid.uuid4(),
        course,
        profile,
    )
    assert blockers == []


@pytest.mark.asyncio
async def test_professional_evidence_requires_trace_before_verification(
    client,
    admin_headers,
):
    professional = await client.post(
        f"{BASE}/professionals",
        json={
            "full_name": "Profissional Evidência",
            "cpf": make_valid_cpf(),
            "qualification": "Engenharia Elétrica",
            "professional_registration": f"REG-{uuid.uuid4().hex[:8]}",
            "council": "TEST",
            "registration_state": "RJ",
        },
        headers=admin_headers,
    )
    assert professional.status_code == 201, professional.text
    professional_id = professional.json()["id"]

    no_trace = await client.post(
        f"{BASE}/professionals/{professional_id}/evidence",
        json={"evidence_type": "PROFICIENCY", "notes": "texto livre"},
        headers=admin_headers,
    )
    assert no_trace.status_code == 201, no_trace.text
    blocked = await client.post(
        f"{BASE}/professionals/{professional_id}/evidence/{no_trace.json()['id']}/decision",
        json={"status": "VERIFIED"},
        headers=admin_headers,
    )
    assert blocked.status_code == 409

    traced = await client.post(
        f"{BASE}/professionals/{professional_id}/evidence",
        json={
            "evidence_type": "PROFICIENCY",
            "document_reference": "urn:test:professional-evidence",
            "issuer": "Autoridade de teste",
        },
        headers=admin_headers,
    )
    assert traced.status_code == 201, traced.text
    verified = await client.post(
        f"{BASE}/professionals/{professional_id}/evidence/{traced.json()['id']}/decision",
        json={"status": "VERIFIED", "notes": "Conferido em teste"},
        headers=admin_headers,
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["status"] == "VERIFIED"
    assert verified.json()["verified_at"] is not None


@pytest.mark.asyncio
async def test_retention_approval_enforces_derived_ead_floor(client, admin_headers):
    course = await client.post(
        "/api/v1/courses/",
        json={
            "code": "NR-RET-FLOOR",
            "name": "Curso de retenção normativa",
            "category": "Compliance",
            "description": "Fixture da política de retenção",
            "carga_horaria": 8,
            "modality": "EAD",
            "tipo_curso": "FORMACAO",
            "price": 0,
        },
        headers=admin_headers,
    )
    assert course.status_code == 201, course.text
    course_id = course.json()["id"]

    profile = await client.put(
        f"{BASE}/courses/{course_id}/profile",
        json={
            "regulatory_standard": "NR-99",
            "regulatory_version": "retention-test-v1",
            "delivery_mode": "EAD",
            "requires_practical_component": False,
            "requires_final_assessment": False,
            "minimum_score": None,
            "validity_period_months": 12,
            "certificate_required_fields": ["student_name"],
            "next_compliance_review_at": (utc_now() + timedelta(days=365)).isoformat(),
        },
        headers=admin_headers,
    )
    assert profile.status_code == 200, profile.text

    requirements = await client.get(
        f"{OPS}/retention-policy/requirements",
        headers=admin_headers,
    )
    assert requirements.status_code == 200, requirements.text
    minimum = requirements.json()["minimum_training_event_retention_days"]
    assert minimum == 1103
    assert requirements.json()["resolved"] is True
    assert requirements.json()["automatic_deletion_enabled"] is False

    draft = await client.post(
        f"{OPS}/retention-policy/versions",
        json={},
        headers=admin_headers,
    )
    assert draft.status_code == 201, draft.text
    version_id = draft.json()["id"]
    common = {
        "certificate_retention_days": 3650,
        "assessment_retention_days": 1825,
        "student_confirmation_retention_days": 1825,
        "practical_evidence_retention_days": 1825,
        "legal_basis": "NR-01 e política interna de teste",
        "purpose": "Preservação de evidências de treinamento",
    }

    below = await client.post(
        f"{OPS}/retention-policy/versions/{version_id}/approve",
        json={**common, "training_event_retention_days": minimum - 1},
        headers=admin_headers,
    )
    assert below.status_code == 409, below.text
    assert any(
        item.startswith("TRAINING_EVENT_RETENTION_BELOW_NORMATIVE_FLOOR")
        for item in below.json()["detail"]["violations"]
    )

    approved = await client.post(
        f"{OPS}/retention-policy/versions/{version_id}/approve",
        json={**common, "training_event_retention_days": minimum},
        headers=admin_headers,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"

    summary = await client.get(f"{OPS}/summary", headers=admin_headers)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["retention_policy_ready"] is True
    assert body["retention_policy_normative_compliant"] is True
    assert body["minimum_training_event_retention_days"] == minimum
    assert body["retention_policy_violations"] == []
    assert body["automatic_deletion_enabled"] is False
