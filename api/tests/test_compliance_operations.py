"""Compliance Operations dashboard, class reporting and retention governance tests.

Covers:
- Authorization: STUDENT blocked, ADMIN/SUPER_ADMIN allowed.
- Tenant isolation: cross-tenant retention versions and class reports are
  not visible across tenants.
- Summary metrics: empty state, regulatory profiles, expired/near reviews,
  enrollments without ledger events, signer profile expiration, retention
  policy readiness.
- Class report: nonexistent class, cross-tenant class, non-regulatory course,
  counts, and admin audit trail registration.
- Retention governance: versioned creation (v1/v2), independent tenants,
  DRAFT edit, APPROVED immutability, approval, idempotent approval, missing
  legal inputs rejection, and concurrent first-version allocation safety.
"""

import asyncio
import hashlib
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select, text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.core.utils import utc_now
from app.models.compliance_retention import ComplianceRetentionPolicyVersion
from app.models.governance import AdminAuditLog
from app.models.tenant import Tenant, TenantStatus
from app.models.training_evidence import EnrollmentComplianceProgress
from app.models.user import User, UserRole
from tests.conftest import make_valid_cpf

BASE = "/api/v1/compliance/operations"


# ─── Helpers ────────────────────────────────────────────────────────────────


async def _admin_id(client, admin_headers):
    response = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert response.status_code == 200, response.text
    return response.json()["id"]


async def _create_regulatory_fixture(
    client,
    admin_headers,
    *,
    code,
    review_at,
    requires_assessment=False,
    requires_practical=False,
    enroll_student=True,
):
    """Create a full regulatory course → class → enrollment chain via the API."""
    course = await client.post(
        "/api/v1/courses/",
        json={
            "code": code,
            "name": f"Curso Compliance Ops {code}",
            "category": "Compliance",
            "description": "Fixture de operações de compliance",
            "carga_horaria": 8,
            "modality": "EAD",
            "tipo_curso": "FORMACAO",
            "price": 0,
        },
        headers=admin_headers,
    )
    assert course.status_code == 201, course.text
    course = course.json()

    professional = await client.post(
        "/api/v1/compliance/professionals",
        json={
            "full_name": f"Profissional {uuid.uuid4().hex[:6]}",
            "cpf": make_valid_cpf(),
            "qualification": "Qualificação de fixture",
            "professional_registration": f"REG-{uuid.uuid4().hex[:6]}",
            "council": "TEST",
            "registration_state": "RJ",
        },
        headers=admin_headers,
    )
    assert professional.status_code == 201, professional.text
    professional = professional.json()

    project = await client.post(
        f"/api/v1/compliance/courses/{course['id']}/projects",
        json={
            "general_objective": "Capacitar para o cenário de teste",
            "specific_objectives": ["Concluir o runtime"],
            "target_audience": "Alunos de homologação",
            "teaching_strategy": "Conteúdo digital",
            "syllabus": ["Conteúdo obrigatório"],
            "workload_hours": 8,
            "delivery_mode": "EAD",
            "materials": ["Material de teste"],
            "assessment_methodology": "Avaliação conforme perfil",
        },
        headers=admin_headers,
    )
    assert project.status_code == 201, project.text
    approved = await client.post(
        f"/api/v1/compliance/courses/{course['id']}/projects/{project.json()['id']}/approve",
        json={"approval_notes": "Fixture aprovada"},
        headers=admin_headers,
    )
    assert approved.status_code == 200, approved.text

    profile = await client.put(
        f"/api/v1/compliance/courses/{course['id']}/profile",
        json={
            "regulatory_standard": "TEST-NR",
            "regulatory_version": "ops-v1",
            "delivery_mode": "EAD",
            "requires_practical_component": requires_practical,
            "requires_final_assessment": requires_assessment,
            "minimum_score": 60 if requires_assessment else None,
            "validity_period_months": 12,
            "certificate_required_fields": ["student_name", "course_name"],
            "technical_responsible_id": professional["id"],
            "pedagogical_project_version_id": approved.json()["id"],
            "next_compliance_review_at": review_at.isoformat(),
        },
        headers=admin_headers,
    )
    assert profile.status_code == 200, profile.text

    ready = await client.post(
        f"/api/v1/compliance/courses/{course['id']}/mark-ready",
        headers=admin_headers,
    )
    assert ready.status_code == 200, ready.text

    admin_id = await _admin_id(client, admin_headers)
    today = utc_now().date()
    class_response = await client.post(
        "/api/v1/classes/",
        json={
            "course_id": course["id"],
            "responsible_admin_id": admin_id,
            "start_date": (today + timedelta(days=1)).isoformat(),
            "end_date": (today + timedelta(days=30)).isoformat(),
            "max_students": 20,
            "status": "ABERTA",
            "description": f"Turma {code}",
        },
        headers=admin_headers,
    )
    assert class_response.status_code == 201, class_response.text

    fixture = {
        "course": course,
        "professional": professional,
        "project": approved.json(),
        "class": class_response.json(),
    }

    if enroll_student:
        student = await client.post(
            "/api/v1/students/",
            json={
                "email": f"ops-{uuid.uuid4().hex[:8]}@example.com",
                "full_name": "Aluno Ops",
                "password": "Ops12345!",
                "cpf": make_valid_cpf(),
            },
            headers=admin_headers,
        )
        assert student.status_code == 201, student.text
        enrollment = await client.post(
            "/api/v1/enrollments/",
            json={
                "student_id": student.json()["id"],
                "class_id": class_response.json()["id"],
                "price": 0,
                "status": "CONFIRMADA",
                "source": "INDIVIDUAL",
            },
            headers=admin_headers,
        )
        assert enrollment.status_code == 201, enrollment.text
        fixture["student"] = student.json()
        fixture["enrollment"] = enrollment.json()
    return fixture


async def _upsert_signing_profile(client, admin_headers, *, not_after):
    response = await client.put(
        "/api/v1/certificate-signing/profile",
        json={
            "provider": "MOCK",
            "enabled": True,
            "signer_display_name": "Signer Ops",
            "certificate_fingerprint_sha256": hashlib.sha256(b"ops-signer").hexdigest(),
            "certificate_not_after": not_after.isoformat() + "Z",
            "provider_metadata": {"max_attempts": 3},
        },
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _seed_alfa_tenant():
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        alfa = Tenant(
            name="Alfa Academy",
            slug="alfa",
            status=TenantStatus.ACTIVE,
            contact_name="Alfa Admin",
            contact_email="admin@alfa.test",
            primary_color="#E86A17",
        )
        db.add(alfa)
        await db.commit()
        await db.refresh(alfa)
        return alfa.id


async def _create_admin_in_tenant(email, tenant_id):
    async with AsyncSessionLocal() as db:
        await db.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        user = User(
            email=email,
            full_name=f"Admin {email}",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=tenant_id,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user.id


def _token(user_id, role, tenant_id):
    return create_access_token(
        {"sub": str(user_id), "role": role, "tenant_id": str(tenant_id)}
    )


async def _insert_orphan_progress(tenant_id, enrollment_id, student_id, course_id):
    """Insert a compliance progress row with NO ledger event (orphan)."""
    async with AsyncSessionLocal() as db:
        await db.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        db.add(
            EnrollmentComplianceProgress(
                tenant_id=tenant_id,
                enrollment_id=enrollment_id,
                student_id=student_id,
                course_id=course_id,
                state="ENROLLED",
                blockers=[],
            )
        )
        await db.commit()


# ─── Authorization ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_student_blocked_from_summary(client, student_user):
    response = await client.get(f"{BASE}/summary", headers=student_user["headers"])
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_student_blocked_from_retention_versions(client, student_user):
    response = await client.get(
        f"{BASE}/retention-policy/versions", headers=student_user["headers"]
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_access_summary(client, admin_headers):
    response = await client.get(f"{BASE}/summary", headers=admin_headers)
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_super_admin_can_access_summary(client, super_admin_headers):
    response = await client.get(f"{BASE}/summary", headers=super_admin_headers)
    assert response.status_code == 200, response.text


# ─── Summary ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_summary_empty_state(client, admin_headers):
    response = await client.get(f"{BASE}/summary", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["course_status_counts"] == {}
    assert body["enrollment_state_counts"] == {}
    assert body["signing_job_status_counts"] == {}
    assert body["reviews_expired"] == 0
    assert body["reviews_due_30_days"] == 0
    assert body["enrollments_without_ledger_events"] == 0
    assert body["signer_profile_enabled"] is False
    assert body["signer_certificate_expired"] is False
    assert body["retention_policy_ready"] is False
    assert body["approved_retention_policy_version"] is None


@pytest.mark.asyncio
async def test_summary_with_regulatory_profile_and_near_review(client, admin_headers):
    await _create_regulatory_fixture(
        client,
        admin_headers,
        code="NR-OPS-NEAR",
        review_at=utc_now() + timedelta(days=15),
    )
    body = (await client.get(f"{BASE}/summary", headers=admin_headers)).json()
    assert body["reviews_expired"] == 0
    assert body["reviews_due_30_days"] >= 1
    assert "COMPLIANCE_READY" in body["course_status_counts"]


@pytest.mark.asyncio
async def test_summary_expired_review(client, admin_headers):
    fixture = await _create_regulatory_fixture(
        client,
        admin_headers,
        code="NR-OPS-EXP",
        review_at=utc_now() + timedelta(days=200),
    )
    # The schema rejects past review dates on creation, so simulate an
    # expired review by backdating the profile row directly.
    async with AsyncSessionLocal() as db:
        await db.execute(text(f"SET LOCAL app.current_tenant = '{WR_TENANT_ID}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        from app.models.compliance import CourseComplianceProfile

        profile = (
            await db.execute(
                select(CourseComplianceProfile).where(
                    CourseComplianceProfile.tenant_id == WR_TENANT_ID,
                    CourseComplianceProfile.course_id == uuid.UUID(fixture["course"]["id"]),
                )
            )
        ).scalar_one()
        profile.next_compliance_review_at = utc_now() - timedelta(days=5)
        await db.commit()
    body = (await client.get(f"{BASE}/summary", headers=admin_headers)).json()
    assert body["reviews_expired"] >= 1


@pytest.mark.asyncio
async def test_summary_enrollments_without_ledger(client, admin_headers):
    fixture = await _create_regulatory_fixture(
        client, admin_headers, code="NR-OPS-LEDGER", review_at=utc_now() + timedelta(days=200)
    )
    # Insert an orphan progress row (no training access event) directly.
    await _insert_orphan_progress(
        WR_TENANT_ID,
        uuid.UUID(fixture["enrollment"]["id"]),
        uuid.UUID(fixture["student"]["id"]),
        uuid.UUID(fixture["course"]["id"]),
    )
    body = (await client.get(f"{BASE}/summary", headers=admin_headers)).json()
    assert body["enrollments_without_ledger_events"] >= 1


@pytest.mark.asyncio
async def test_summary_signer_profile_expired(client, admin_headers):
    # The signing profile API rejects already-expired certificates, so seed
    # an expired profile directly to exercise the summary's expired detection.
    async with AsyncSessionLocal() as db:
        await db.execute(text(f"SET LOCAL app.current_tenant = '{WR_TENANT_ID}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        from app.models.certificate_signing import CertificateSigningProfile

        db.add(
            CertificateSigningProfile(
                tenant_id=WR_TENANT_ID,
                provider="MOCK",
                enabled=True,
                signer_display_name="Expired Signer",
                certificate_not_after=utc_now() - timedelta(days=1),
                provider_metadata={},
            )
        )
        await db.commit()
    body = (await client.get(f"{BASE}/summary", headers=admin_headers)).json()
    assert body["signer_profile_enabled"] is True
    assert body["signer_certificate_expired"] is True


@pytest.mark.asyncio
async def test_summary_signer_profile_expires_soon(client, admin_headers):
    await _upsert_signing_profile(
        client, admin_headers, not_after=utc_now() + timedelta(days=10)
    )
    body = (await client.get(f"{BASE}/summary", headers=admin_headers)).json()
    assert body["signer_certificate_expired"] is False
    assert body["signer_certificate_expires_30_days"] is True


@pytest.mark.asyncio
async def test_summary_reflects_approved_retention_policy(client, admin_headers):
    created = (
        await client.post(f"{BASE}/retention-policy/versions", json={}, headers=admin_headers)
    ).json()
    await client.post(
        f"{BASE}/retention-policy/versions/{created['id']}/approve",
        json={
            "certificate_retention_days": 3650,
            "assessment_retention_days": 1825,
            "training_event_retention_days": 1825,
            "student_confirmation_retention_days": 1825,
            "practical_evidence_retention_days": 1825,
            "legal_basis": "Base legal de teste documentada",
            "purpose": "Finalidade de teste documentada",
        },
        headers=admin_headers,
    )
    body = (await client.get(f"{BASE}/summary", headers=admin_headers)).json()
    assert body["retention_policy_ready"] is True
    assert body["approved_retention_policy_version"] == 1


# ─── Class report ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_class_report_not_found(client, admin_headers):
    response = await client.get(
        f"{BASE}/classes/{uuid.uuid4()}/report", headers=admin_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_class_report_non_regulatory_course(client, admin_headers):
    today = utc_now().date()
    course = await client.post(
        "/api/v1/courses/",
        json={
            "code": "NON-REG-OPS",
            "name": "Curso não regulatório",
            "category": "Geral",
            "carga_horaria": 4,
            "modality": "EAD",
            "price": 0,
            "description": "Curso sem perfil regulatório",
        },
        headers=admin_headers,
    )
    assert course.status_code == 201
    admin_id = await _admin_id(client, admin_headers)
    cls = await client.post(
        "/api/v1/classes/",
        json={
            "course_id": course.json()["id"],
            "responsible_admin_id": admin_id,
            "start_date": (today + timedelta(days=1)).isoformat(),
            "end_date": (today + timedelta(days=30)).isoformat(),
            "max_students": 10,
            "status": "ABERTA",
        },
        headers=admin_headers,
    )
    assert cls.status_code == 201
    response = await client.get(
        f"{BASE}/classes/{cls.json()['id']}/report", headers=admin_headers
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_class_report_counts_and_audit_trail(client, admin_headers):
    fixture = await _create_regulatory_fixture(
        client, admin_headers, code="NR-OPS-REPORT", review_at=utc_now() + timedelta(days=200)
    )
    class_id = fixture["class"]["id"]
    response = await client.get(
        f"{BASE}/classes/{class_id}/report", headers=admin_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["class_id"] == class_id
    assert body["course_code"] == "NR-OPS-REPORT"
    assert body["enrollment_count"] == 1
    assert isinstance(body["enrollment_state_counts"], dict)
    assert isinstance(body["certificate_status_counts"], dict)
    assert isinstance(body["signing_job_status_counts"], dict)

    # Audit trail: a read access was recorded in the admin audit log.
    async with AsyncSessionLocal() as db:
        await db.execute(text(f"SET LOCAL app.current_tenant = '{WR_TENANT_ID}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        rows = (
            await db.execute(
                select(AdminAuditLog).where(
                    AdminAuditLog.path.like(f"%/classes/{class_id}/report%")
                )
            )
        ).scalars().all()
    assert len(rows) >= 1
    assert rows[0].method == "GET"
    assert rows[0].status_code == 200


@pytest.mark.asyncio
async def test_class_report_cross_tenant_denied(client, admin_headers):
    alfa_id = await _seed_alfa_tenant()
    # Create a regulatory class in Alfa directly via DB.
    async with AsyncSessionLocal() as db:
        await db.execute(text(f"SET LOCAL app.current_tenant = '{alfa_id}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        from app.models.class_model import Class, ClassStatus
        from app.models.course import Course, CourseModality, CourseType

        admin_user = User(
            email=f"alfa-admin-{uuid.uuid4().hex[:6]}@alfa.test",
            full_name="Alfa Admin",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=alfa_id,
        )
        db.add(admin_user)
        await db.flush()
        course = Course(
            tenant_id=alfa_id,
            code="ALFA-OPS-01",
            name="Alfa Ops Course",
            category="Compliance",
            carga_horaria=8,
            modality=CourseModality.EAD,
            tipo_curso=CourseType.FORMACAO,
            price=0,
        )
        db.add(course)
        await db.flush()
        cls = Class(
            tenant_id=alfa_id,
            course_id=course.id,
            responsible_admin_id=admin_user.id,
            start_date=utc_now().date() + timedelta(days=1),
            end_date=utc_now().date() + timedelta(days=30),
            max_students=10,
            status=ClassStatus.ABERTA,
        )
        db.add(cls)
        await db.commit()
        await db.refresh(cls)
        alfa_class_id = cls.id

    # WR admin queries the Alfa class → 404 (tenant scoped).
    response = await client.get(
        f"{BASE}/classes/{alfa_class_id}/report", headers=admin_headers
    )
    assert response.status_code == 404


# ─── Retention governance ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_retention_create_v1_and_v2(client, admin_headers):
    v1 = (
        await client.post(f"{BASE}/retention-policy/versions", json={}, headers=admin_headers)
    ).json()
    assert v1["version"] == 1
    assert v1["status"] == "DRAFT"
    v2 = (
        await client.post(f"{BASE}/retention-policy/versions", json={}, headers=admin_headers)
    ).json()
    assert v2["version"] == 2
    versions = (
        await client.get(f"{BASE}/retention-policy/versions", headers=admin_headers)
    ).json()
    assert [v["version"] for v in versions] == [2, 1]


@pytest.mark.asyncio
async def test_retention_independent_tenants(client, admin_headers):
    alfa_id = await _seed_alfa_tenant()
    alfa_admin_id = await _create_admin_in_tenant("alfa-retention@alfa.test", alfa_id)
    alfa_headers = {
        "Authorization": f"Bearer {_token(alfa_admin_id, 'admin', alfa_id)}",
        "X-Tenant-Id": str(alfa_id),
    }

    wr_v1 = (
        await client.post(f"{BASE}/retention-policy/versions", json={}, headers=admin_headers)
    ).json()
    alfa_v1 = (
        await client.post(f"{BASE}/retention-policy/versions", json={}, headers=alfa_headers)
    ).json()
    assert wr_v1["version"] == 1
    assert alfa_v1["version"] == 1
    assert wr_v1["id"] != alfa_v1["id"]

    # WR admin cannot see Alfa versions.
    wr_versions = (
        await client.get(f"{BASE}/retention-policy/versions", headers=admin_headers)
    ).json()
    assert all(v["id"] != alfa_v1["id"] for v in wr_versions)


@pytest.mark.asyncio
async def test_retention_edit_draft(client, admin_headers):
    created = (
        await client.post(f"{BASE}/retention-policy/versions", json={}, headers=admin_headers)
    ).json()
    updated = (
        await client.patch(
            f"{BASE}/retention-policy/versions/{created['id']}",
            json={
                "certificate_retention_days": 3650,
                "legal_basis": "Base legal de teste",
                "purpose": "Finalidade de teste",
            },
            headers=admin_headers,
        )
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["certificate_retention_days"] == 3650
    assert updated.json()["legal_basis"] == "Base legal de teste"


@pytest.mark.asyncio
async def test_retention_approved_is_immutable(client, admin_headers):
    created = (
        await client.post(f"{BASE}/retention-policy/versions", json={}, headers=admin_headers)
    ).json()
    await client.post(
        f"{BASE}/retention-policy/versions/{created['id']}/approve",
        json={
            "certificate_retention_days": 3650,
            "assessment_retention_days": 1825,
            "training_event_retention_days": 1825,
            "student_confirmation_retention_days": 1825,
            "practical_evidence_retention_days": 1825,
            "legal_basis": "Base legal",
            "purpose": "Finalidade",
        },
        headers=admin_headers,
    )
    blocked = await client.patch(
        f"{BASE}/retention-policy/versions/{created['id']}",
        json={"certificate_retention_days": 1},
        headers=admin_headers,
    )
    assert blocked.status_code == 409


@pytest.mark.asyncio
async def test_retention_approve_valid(client, admin_headers):
    created = (
        await client.post(f"{BASE}/retention-policy/versions", json={}, headers=admin_headers)
    ).json()
    approved = await client.post(
        f"{BASE}/retention-policy/versions/{created['id']}/approve",
        json={
            "certificate_retention_days": 3650,
            "assessment_retention_days": 1825,
            "training_event_retention_days": 1825,
            "student_confirmation_retention_days": 1825,
            "practical_evidence_retention_days": 1825,
            "legal_basis": "Base legal",
            "purpose": "Finalidade",
        },
        headers=admin_headers,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"
    assert approved.json()["approved_at"] is not None


@pytest.mark.asyncio
async def test_retention_approve_idempotent(client, admin_headers):
    created = (
        await client.post(f"{BASE}/retention-policy/versions", json={}, headers=admin_headers)
    ).json()
    payload = {
        "certificate_retention_days": 3650,
        "assessment_retention_days": 1825,
        "training_event_retention_days": 1825,
        "student_confirmation_retention_days": 1825,
        "practical_evidence_retention_days": 1825,
        "legal_basis": "Base legal",
        "purpose": "Finalidade",
    }
    first = await client.post(
        f"{BASE}/retention-policy/versions/{created['id']}/approve",
        json=payload,
        headers=admin_headers,
    )
    assert first.status_code == 200
    second = await client.post(
        f"{BASE}/retention-policy/versions/{created['id']}/approve",
        json=payload,
        headers=admin_headers,
    )
    assert second.status_code == 200
    assert second.json()["status"] == "APPROVED"


@pytest.mark.asyncio
async def test_retention_approve_rejects_missing_legal_basis(client, admin_headers):
    created = (
        await client.post(f"{BASE}/retention-policy/versions", json={}, headers=admin_headers)
    ).json()
    response = await client.post(
        f"{BASE}/retention-policy/versions/{created['id']}/approve",
        json={
            "certificate_retention_days": 3650,
            "assessment_retention_days": 1825,
            "training_event_retention_days": 1825,
            "student_confirmation_retention_days": 1825,
            "practical_evidence_retention_days": 1825,
            "purpose": "Finalidade",
        },
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert "legal_basis" in response.json()["detail"]["missing"]


@pytest.mark.asyncio
async def test_retention_approve_rejects_missing_purpose(client, admin_headers):
    created = (
        await client.post(f"{BASE}/retention-policy/versions", json={}, headers=admin_headers)
    ).json()
    response = await client.post(
        f"{BASE}/retention-policy/versions/{created['id']}/approve",
        json={
            "certificate_retention_days": 3650,
            "assessment_retention_days": 1825,
            "training_event_retention_days": 1825,
            "student_confirmation_retention_days": 1825,
            "practical_evidence_retention_days": 1825,
            "legal_basis": "Base legal",
        },
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert "purpose" in response.json()["detail"]["missing"]


@pytest.mark.asyncio
async def test_retention_approve_rejects_missing_retention_period(client, admin_headers):
    created = (
        await client.post(f"{BASE}/retention-policy/versions", json={}, headers=admin_headers)
    ).json()
    response = await client.post(
        f"{BASE}/retention-policy/versions/{created['id']}/approve",
        json={
            "certificate_retention_days": 3650,
            "legal_basis": "Base legal",
            "purpose": "Finalidade",
        },
        headers=admin_headers,
    )
    assert response.status_code == 409
    missing = response.json()["detail"]["missing"]
    assert "assessment_retention_days" in missing
    assert "training_event_retention_days" in missing
    assert "student_confirmation_retention_days" in missing
    assert "practical_evidence_retention_days" in missing


@pytest.mark.asyncio
async def test_retention_no_automatic_purge_flag(client, admin_headers):
    created = (
        await client.post(f"{BASE}/retention-policy/versions", json={}, headers=admin_headers)
    ).json()
    response = await client.post(
        f"{BASE}/retention-policy/versions/{created['id']}/approve",
        json={
            "certificate_retention_days": 3650,
            "assessment_retention_days": 1825,
            "training_event_retention_days": 1825,
            "student_confirmation_retention_days": 1825,
            "practical_evidence_retention_days": 1825,
            "legal_basis": "Base legal",
            "purpose": "Finalidade",
        },
        headers=admin_headers,
    )
    # Approval must never enable automatic deletion.
    assert response.json().get("automatic_deletion_enabled", False) is False


@pytest.mark.asyncio
async def test_retention_concurrent_first_version_no_500(client, admin_headers):
    """Two concurrent first-version allocations must not collide with a 500.

    The tenant row lock serializes allocation; both requests succeed with
    distinct, sequential versions.
    """
    results = await asyncio.gather(
        client.post(f"{BASE}/retention-policy/versions", json={}, headers=admin_headers),
        client.post(f"{BASE}/retention-policy/versions", json={}, headers=admin_headers),
        client.post(f"{BASE}/retention-policy/versions", json={}, headers=admin_headers),
    )
    statuses = [r.status_code for r in results]
    assert all(s == 201 for s in statuses), statuses
    versions = sorted(r.json()["version"] for r in results)
    assert versions == [1, 2, 3]


@pytest.mark.asyncio
async def test_retention_update_not_found_cross_tenant(client, admin_headers):
    alfa_id = await _seed_alfa_tenant()
    alfa_admin_id = await _create_admin_in_tenant("alfa-x@alfa.test", alfa_id)
    alfa_headers = {
        "Authorization": f"Bearer {_token(alfa_admin_id, 'admin', alfa_id)}",
        "X-Tenant-Id": str(alfa_id),
    }
    alfa_created = (
        await client.post(f"{BASE}/retention-policy/versions", json={}, headers=alfa_headers)
    ).json()
    # WR admin cannot edit Alfa's version → 404.
    response = await client.patch(
        f"{BASE}/retention-policy/versions/{alfa_created['id']}",
        json={"legal_basis": "x"},
        headers=admin_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_retention_create_payload_validation_rejects_non_positive(client, admin_headers):
    # gt=0 on the schema rejects zero/negative retention days.
    response = await client.post(
        f"{BASE}/retention-policy/versions",
        json={"certificate_retention_days": 0},
        headers=admin_headers,
    )
    assert response.status_code == 422
