"""Certificate tenant isolation tests.

Verifies the authorization contract:
- Tenant ADMIN: may list/get/download/delete ONLY own-tenant certificates.
- SUPER_ADMIN: behaves as tenant admin on /certificates routes — same
  resolved tenant only, cross-tenant is 404.
- STUDENT: may get/download ONLY their own certificate in the resolved tenant.
- Other student same tenant: 403.
- Cross-tenant (any role): 404 (non-disclosing).
- Cross-tenant create: 404 (enrollment not found in tenant).
- Cross-tenant delete: 404.
- Public validation: allowed without auth.
- PDF branding: WR cert has WR identity, Alfa cert has Alfa identity.
- Tenant-aware validation URL: derived from trusted request Origin.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy import text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.models.certificate import Certificate
from app.models.class_model import Class, ClassStatus
from app.models.course import Course, CourseModality, CourseType
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.student import Student
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User, UserRole


async def _seed_alfa_tenant():
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await db.execute(text(f"SET LOCAL app.current_tenant = '{WR_TENANT_ID}'"))
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


async def _create_admin(email, tenant_id):
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = tenant_id
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


async def _create_student(email, full_name, tenant_id):
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = tenant_id
        await db.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        user = User(
            email=email,
            full_name=full_name,
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.STUDENT,
            is_active=True,
            tenant_id=tenant_id,
        )
        db.add(user)
        await db.flush()

        student = Student(
            user_id=user.id,
            tenant_id=tenant_id,
            cpf=str(uuid.uuid4().int)[:11],
        )
        db.add(student)
        await db.commit()
        await db.refresh(student)
        await db.refresh(user)
        return user.id, student.id


async def _create_course_class_enrollment_cert(
    tenant_id, student_id, course_code, course_name
):
    """Create a full course → class → enrollment → certificate chain in one tenant."""
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = tenant_id
        await db.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))

        # Create an admin user for the class responsible_admin_id
        admin_user = User(
            email=f"admin_{course_code}@test.com",
            full_name=f"Admin {course_code}",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=tenant_id,
        )
        db.add(admin_user)
        await db.flush()

        course = Course(
            tenant_id=tenant_id,
            code=course_code,
            name=course_name,
            category="Test",
            carga_horaria=8,
            modality=CourseModality.EAD,
            tipo_curso=CourseType.FORMACAO,
            price=99.90,
        )
        db.add(course)
        await db.flush()

        cls = Class(
            tenant_id=tenant_id,
            course_id=course.id,
            responsible_admin_id=admin_user.id,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            max_students=20,
            status=ClassStatus.ABERTA,
        )
        db.add(cls)
        await db.flush()

        enrollment = Enrollment(
            tenant_id=tenant_id,
            student_id=student_id,
            class_id=cls.id,
            price=99.90,
            status=EnrollmentStatus.CONCLUIDA,
        )
        db.add(enrollment)
        await db.flush()

        cert = Certificate(
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            certificate_number=f"CERT-{uuid.uuid4().hex[:12].upper()}",
            validation_code=uuid.uuid4().hex[:16].upper(),
        )
        db.add(cert)
        await db.commit()
        await db.refresh(cert)
        return cert.id, course.id


def _token(user_id, role, tenant_id):
    return create_access_token(
        {"sub": str(user_id), "role": role, "tenant_id": str(tenant_id)}
    )


# ─── List isolation ───

@pytest.mark.asyncio
async def test_wr_admin_lists_wr_only(client):
    """WR admin listando certificados vê apenas certificados WR."""
    alfa_id = await _seed_alfa_tenant()

    _wr_student_uid, wr_student_sid = await _create_student(
        "wrstu@wr.test", "WR Student", WR_TENANT_ID
    )
    _alfa_student_uid, alfa_student_sid = await _create_student(
        "alfastu@alfa.test", "Alfa Student", alfa_id
    )

    wr_cert_id, _ = await _create_course_class_enrollment_cert(
        WR_TENANT_ID, wr_student_sid, "WR-CERT-01", "WR Cert Course"
    )
    alfa_cert_id, _ = await _create_course_class_enrollment_cert(
        alfa_id, alfa_student_sid, "ALFA-CERT-01", "Alfa Cert Course"
    )

    wr_admin_id = await _create_admin("wrlist@wr.test", WR_TENANT_ID)
    token = _token(wr_admin_id, "admin", WR_TENANT_ID)

    resp = await client.get(
        "/api/v1/certificates/",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200
    cert_ids = [c["id"] for c in resp.json()]
    assert str(wr_cert_id) in cert_ids
    assert str(alfa_cert_id) not in cert_ids, "WR admin should NOT see Alfa certificates"


@pytest.mark.asyncio
async def test_alfa_admin_lists_alfa_only(client):
    """Alfa admin listando certificados vê apenas certificados Alfa."""
    alfa_id = await _seed_alfa_tenant()

    _wr_student_uid, wr_student_sid = await _create_student(
        "wrstu2@wr.test", "WR Student 2", WR_TENANT_ID
    )
    _alfa_student_uid, alfa_student_sid = await _create_student(
        "alfastu2@alfa.test", "Alfa Student 2", alfa_id
    )

    wr_cert_id, _ = await _create_course_class_enrollment_cert(
        WR_TENANT_ID, wr_student_sid, "WR-CERT-02", "WR Cert Course 2"
    )
    alfa_cert_id, _ = await _create_course_class_enrollment_cert(
        alfa_id, alfa_student_sid, "ALFA-CERT-02", "Alfa Cert Course 2"
    )

    alfa_admin_id = await _create_admin("alfalist@alfa.test", alfa_id)
    token = _token(alfa_admin_id, "admin", alfa_id)

    resp = await client.get(
        "/api/v1/certificates/",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "alfa"},
    )
    assert resp.status_code == 200
    cert_ids = [c["id"] for c in resp.json()]
    assert str(alfa_cert_id) in cert_ids
    assert str(wr_cert_id) not in cert_ids, "Alfa admin should NOT see WR certificates"


# ─── GET isolation ───

@pytest.mark.asyncio
async def test_wr_admin_get_alfa_cert_denied(client):
    """WR admin tentando GET certificado Alfa → 404 (non-disclosing)."""
    alfa_id = await _seed_alfa_tenant()
    _, alfa_student_sid = await _create_student(
        "alfaget@alfa.test", "Alfa Get Student", alfa_id
    )
    alfa_cert_id, _ = await _create_course_class_enrollment_cert(
        alfa_id, alfa_student_sid, "ALFA-GET-01", "Alfa Get Course"
    )

    wr_admin_id = await _create_admin("wrget@wr.test", WR_TENANT_ID)
    token = _token(wr_admin_id, "admin", WR_TENANT_ID)

    resp = await client.get(
        f"/api/v1/certificates/{alfa_cert_id}",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_alfa_admin_get_wr_cert_denied(client):
    """Alfa admin tentando GET certificado WR → 404 (non-disclosing)."""
    alfa_id = await _seed_alfa_tenant()
    _, wr_student_sid = await _create_student(
        "wrget2@wr.test", "WR Get Student 2", WR_TENANT_ID
    )
    wr_cert_id, _ = await _create_course_class_enrollment_cert(
        WR_TENANT_ID, wr_student_sid, "WR-GET-01", "WR Get Course"
    )

    alfa_admin_id = await _create_admin("alfaget2@alfa.test", alfa_id)
    token = _token(alfa_admin_id, "admin", alfa_id)

    resp = await client.get(
        f"/api/v1/certificates/{wr_cert_id}",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "alfa"},
    )
    assert resp.status_code == 404


# ─── Download isolation ───

@pytest.mark.asyncio
async def test_wr_admin_download_alfa_cert_denied(client):
    """WR admin tentando baixar certificado Alfa → 404."""
    alfa_id = await _seed_alfa_tenant()
    _, alfa_student_sid = await _create_student(
        "alfadl@alfa.test", "Alfa DL Student", alfa_id
    )
    alfa_cert_id, _ = await _create_course_class_enrollment_cert(
        alfa_id, alfa_student_sid, "ALFA-DL-01", "Alfa DL Course"
    )

    wr_admin_id = await _create_admin("wrdl@wr.test", WR_TENANT_ID)
    token = _token(wr_admin_id, "admin", WR_TENANT_ID)

    resp = await client.get(
        f"/api/v1/certificates/{alfa_cert_id}/download",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_alfa_admin_download_wr_cert_denied(client):
    """Alfa admin tentando baixar certificado WR → 404."""
    alfa_id = await _seed_alfa_tenant()
    _, wr_student_sid = await _create_student(
        "wrdl2@wr.test", "WR DL Student 2", WR_TENANT_ID
    )
    wr_cert_id, _ = await _create_course_class_enrollment_cert(
        WR_TENANT_ID, wr_student_sid, "WR-DL-01", "WR DL Course"
    )

    alfa_admin_id = await _create_admin("alfadl2@alfa.test", alfa_id)
    token = _token(alfa_admin_id, "admin", alfa_id)

    resp = await client.get(
        f"/api/v1/certificates/{wr_cert_id}/download",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "alfa"},
    )
    assert resp.status_code == 404


# ─── Student access ───

@pytest.mark.asyncio
async def test_student_downloads_own_cert_allowed(client):
    """Student pode baixar seu próprio certificado → 200."""
    wr_student_uid, wr_student_sid = await _create_student(
        "wrstuown@wr.test", "WR Own Student", WR_TENANT_ID
    )
    cert_id, _ = await _create_course_class_enrollment_cert(
        WR_TENANT_ID, wr_student_sid, "WR-OWN-01", "WR Own Course"
    )

    token = _token(wr_student_uid, "student", WR_TENANT_ID)

    resp = await client.get(
        f"/api/v1/certificates/{cert_id}/download",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_other_student_same_tenant_denied(client):
    """Outro estudante do mesmo tenant → 403 no download, 403 no get."""
    _stu1_uid, stu1_sid = await _create_student(
        "wrstu1@wr.test", "WR Student 1", WR_TENANT_ID
    )
    stu2_uid, _ = await _create_student(
        "wrstu2b@wr.test", "WR Student 2", WR_TENANT_ID
    )
    cert_id, _ = await _create_course_class_enrollment_cert(
        WR_TENANT_ID, stu1_sid, "WR-OTH-01", "WR Other Course"
    )

    token2 = _token(stu2_uid, "student", WR_TENANT_ID)

    resp_dl = await client.get(
        f"/api/v1/certificates/{cert_id}/download",
        headers={"Authorization": f"Bearer {token2}", "x-tenant-slug": "wr"},
    )
    assert resp_dl.status_code == 403

    resp_get = await client.get(
        f"/api/v1/certificates/{cert_id}",
        headers={"Authorization": f"Bearer {token2}", "x-tenant-slug": "wr"},
    )
    assert resp_get.status_code == 403


@pytest.mark.asyncio
async def test_cross_tenant_student_denied(client):
    """Estudante cross-tenant → 404 (non-disclosing)."""
    alfa_id = await _seed_alfa_tenant()
    _, wr_student_sid = await _create_student(
        "wrstuxt@wr.test", "WR XT Student", WR_TENANT_ID
    )
    alfa_student_uid2, _ = await _create_student(
        "alfastuxt@alfa.test", "Alfa XT Student", alfa_id
    )
    wr_cert_id, _ = await _create_course_class_enrollment_cert(
        WR_TENANT_ID, wr_student_sid, "WR-XT-01", "WR XT Course"
    )

    alfa_token = _token(alfa_student_uid2, "student", alfa_id)

    resp = await client.get(
        f"/api/v1/certificates/{wr_cert_id}/download",
        headers={"Authorization": f"Bearer {alfa_token}", "x-tenant-slug": "alfa"},
    )
    assert resp.status_code == 404


# ─── Create isolation ───

@pytest.mark.asyncio
async def test_cross_tenant_create_denied(client):
    """Admin não pode criar certificado para matrícula de outro tenant → 404."""
    alfa_id = await _seed_alfa_tenant()

    # Create WR enrollment
    _, wr_student_sid = await _create_student(
        "wrstucr@wr.test", "WR CR Student", WR_TENANT_ID
    )
    _, wr_course_id = await _create_course_class_enrollment_cert(
        WR_TENANT_ID, wr_student_sid, "WR-CR-01", "WR CR Course"
    )

    # Get the WR enrollment ID (the cert was already created, so we need a new enrollment)
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await db.execute(text(f"SET LOCAL app.current_tenant = '{WR_TENANT_ID}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        from sqlalchemy import select as sel

        from app.models.class_model import Class as ClassModel

        cls = (
            await db.execute(
                sel(ClassModel).where(ClassModel.course_id == wr_course_id)
            )
        ).scalar_one()

        # Create a second enrollment without certificate
        new_enrollment = Enrollment(
            tenant_id=WR_TENANT_ID,
            student_id=wr_student_sid,
            class_id=cls.id,
            price=99.90,
            status=EnrollmentStatus.CONCLUIDA,
        )
        # Use a different student to avoid unique constraint on enrollment_id
        _, another_student_sid = await _create_student(
            "wrstucr2@wr.test", "WR CR Student 2", WR_TENANT_ID
        )
        new_enrollment.student_id = another_student_sid
        db.add(new_enrollment)
        await db.commit()
        await db.refresh(new_enrollment)
        wr_enrollment_id = new_enrollment.id

    # Alfa admin tries to create certificate for WR enrollment
    alfa_admin_id = await _create_admin("alfacr@alfa.test", alfa_id)
    token = _token(alfa_admin_id, "admin", alfa_id)

    resp = await client.post(
        "/api/v1/certificates/",
        json={"enrollment_id": str(wr_enrollment_id)},
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "alfa"},
    )
    assert resp.status_code == 404, "Alfa admin should NOT create cert for WR enrollment"


# ─── Delete isolation ───

@pytest.mark.asyncio
async def test_cross_tenant_delete_denied(client):
    """Admin não pode deletar certificado de outro tenant → 404."""
    alfa_id = await _seed_alfa_tenant()
    _, wr_student_sid = await _create_student(
        "wrstudl@wr.test", "WR DL Student", WR_TENANT_ID
    )
    wr_cert_id, _ = await _create_course_class_enrollment_cert(
        WR_TENANT_ID, wr_student_sid, "WR-DEL-01", "WR DEL Course"
    )

    alfa_admin_id = await _create_admin("alfadl3@alfa.test", alfa_id)
    token = _token(alfa_admin_id, "admin", alfa_id)

    resp = await client.delete(
        f"/api/v1/certificates/{wr_cert_id}",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "alfa"},
    )
    assert resp.status_code == 404


# ─── Public validation ───

@pytest.mark.asyncio
async def test_public_validation_allowed(client):
    """Validação pública sem autenticação → 200 com valid=True."""
    _, wr_student_sid = await _create_student(
        "wrstuval@wr.test", "WR Val Student", WR_TENANT_ID
    )
    cert_id, _ = await _create_course_class_enrollment_cert(
        WR_TENANT_ID, wr_student_sid, "WR-VAL-01", "WR Val Course"
    )

    # Get the validation code
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await db.execute(text(f"SET LOCAL app.current_tenant = '{WR_TENANT_ID}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        from sqlalchemy import select as sel

        from app.models.certificate import Certificate as CertModel

        cert = (
            await db.execute(sel(CertModel).where(CertModel.id == cert_id))
        ).scalar_one()
        validation_code = cert.validation_code

    # Public validation — no auth header
    resp = await client.post(
        "/api/v1/certificates/validate",
        json={"validation_code": validation_code},
    )
    assert resp.status_code == 200
    assert resp.json()["valid"] is True
    assert resp.json()["student_name"] == "WR Val Student"
    assert resp.json()["course_name"] == "WR Val Course"


# ─── SUPER_ADMIN behavior ───
# SUPER_ADMIN must behave as a tenant admin on regular /certificates routes.
# No implicit cross-tenant privilege. Global management requires /super-admin/.

async def _create_super_admin(email, tenant_id):
    """Create a SUPER_ADMIN user bound to tenant_id."""
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = tenant_id
        await db.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        user = User(
            email=email,
            full_name=f"SuperAdmin {email}",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            tenant_id=tenant_id,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user.id


@pytest.mark.asyncio
async def test_super_admin_wr_context_list_wr_only(client):
    """SUPER_ADMIN in WR context list → WR certificates only."""
    alfa_id = await _seed_alfa_tenant()
    _, wr_student_sid = await _create_student(
        "sawrlist@wr.test", "SA WR List Student", WR_TENANT_ID
    )
    _, alfa_student_sid = await _create_student(
        "saalfalist@alfa.test", "SA Alfa List Student", alfa_id
    )
    wr_cert_id, _ = await _create_course_class_enrollment_cert(
        WR_TENANT_ID, wr_student_sid, "SA-WR-LIST-01", "SA WR List Course"
    )
    alfa_cert_id, _ = await _create_course_class_enrollment_cert(
        alfa_id, alfa_student_sid, "SA-ALFA-LIST-01", "SA Alfa List Course"
    )

    sa_id = await _create_super_admin("sawr@wr.test", WR_TENANT_ID)
    token = _token(sa_id, "super_admin", WR_TENANT_ID)

    resp = await client.get(
        "/api/v1/certificates/",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200
    cert_ids = [c["id"] for c in resp.json()]
    assert str(wr_cert_id) in cert_ids
    assert str(alfa_cert_id) not in cert_ids, \
        "SUPER_ADMIN in WR context must NOT see Alfa certificates"


@pytest.mark.asyncio
async def test_super_admin_wr_context_get_wr_allowed(client):
    """SUPER_ADMIN in WR context GET WR cert → 200."""
    _, wr_student_sid = await _create_student(
        "sawrget@wr.test", "SA WR Get Student", WR_TENANT_ID
    )
    cert_id, _ = await _create_course_class_enrollment_cert(
        WR_TENANT_ID, wr_student_sid, "SA-WR-GET-01", "SA WR Get Course"
    )

    sa_id = await _create_super_admin("sawrget2@wr.test", WR_TENANT_ID)
    token = _token(sa_id, "super_admin", WR_TENANT_ID)

    resp = await client.get(
        f"/api/v1/certificates/{cert_id}",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == str(cert_id)


@pytest.mark.asyncio
async def test_super_admin_wr_context_get_alfa_denied(client):
    """SUPER_ADMIN in WR context GET Alfa cert → 404."""
    alfa_id = await _seed_alfa_tenant()
    _, alfa_student_sid = await _create_student(
        "saalfaget@alfa.test", "SA Alfa Get Student", alfa_id
    )
    alfa_cert_id, _ = await _create_course_class_enrollment_cert(
        alfa_id, alfa_student_sid, "SA-ALFA-GET-01", "SA Alfa Get Course"
    )

    sa_id = await _create_super_admin("sawrget3@wr.test", WR_TENANT_ID)
    token = _token(sa_id, "super_admin", WR_TENANT_ID)

    resp = await client.get(
        f"/api/v1/certificates/{alfa_cert_id}",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_super_admin_wr_context_download_wr_allowed(client):
    """SUPER_ADMIN in WR context download WR cert → 200."""
    _, wr_student_sid = await _create_student(
        "sawrdl@wr.test", "SA WR DL Student", WR_TENANT_ID
    )
    cert_id, _ = await _create_course_class_enrollment_cert(
        WR_TENANT_ID, wr_student_sid, "SA-WR-DL-01", "SA WR DL Course"
    )

    sa_id = await _create_super_admin("sawrdl2@wr.test", WR_TENANT_ID)
    token = _token(sa_id, "super_admin", WR_TENANT_ID)

    resp = await client.get(
        f"/api/v1/certificates/{cert_id}/download",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_super_admin_wr_context_download_alfa_denied(client):
    """SUPER_ADMIN in WR context download Alfa cert → 404."""
    alfa_id = await _seed_alfa_tenant()
    _, alfa_student_sid = await _create_student(
        "saalfadl@alfa.test", "SA Alfa DL Student", alfa_id
    )
    alfa_cert_id, _ = await _create_course_class_enrollment_cert(
        alfa_id, alfa_student_sid, "SA-ALFA-DL-01", "SA Alfa DL Course"
    )

    sa_id = await _create_super_admin("sawrdl3@wr.test", WR_TENANT_ID)
    token = _token(sa_id, "super_admin", WR_TENANT_ID)

    resp = await client.get(
        f"/api/v1/certificates/{alfa_cert_id}/download",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_super_admin_wr_context_delete_alfa_denied(client):
    """SUPER_ADMIN in WR context delete Alfa cert → 404."""
    alfa_id = await _seed_alfa_tenant()
    _, alfa_student_sid = await _create_student(
        "saalfadel@alfa.test", "SA Alfa Del Student", alfa_id
    )
    alfa_cert_id, _ = await _create_course_class_enrollment_cert(
        alfa_id, alfa_student_sid, "SA-ALFA-DEL-01", "SA Alfa Del Course"
    )

    sa_id = await _create_super_admin("sawrdel@wr.test", WR_TENANT_ID)
    token = _token(sa_id, "super_admin", WR_TENANT_ID)

    resp = await client.delete(
        f"/api/v1/certificates/{alfa_cert_id}",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_super_admin_wr_context_create_alfa_enrollment_denied(client):
    """SUPER_ADMIN in WR context create cert for Alfa enrollment → 404."""
    alfa_id = await _seed_alfa_tenant()

    # Create Alfa enrollment (without certificate)
    _, alfa_student_sid = await _create_student(
        "saalfacr@alfa.test", "SA Alfa CR Student", alfa_id
    )
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = alfa_id
        await db.execute(text(f"SET LOCAL app.current_tenant = '{alfa_id}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        admin_user = User(
            email=f"saadmin_{uuid.uuid4().hex[:6]}@alfa.test",
            full_name="SA Alfa Admin",
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
            code=f"SA-ALFA-CR-{uuid.uuid4().hex[:4].upper()}",
            name="SA Alfa CR Course",
            category="Test",
            carga_horaria=8,
            modality=CourseModality.EAD,
            tipo_curso=CourseType.FORMACAO,
            price=99.90,
        )
        db.add(course)
        await db.flush()
        cls = Class(
            tenant_id=alfa_id,
            course_id=course.id,
            responsible_admin_id=admin_user.id,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            max_students=20,
            status=ClassStatus.ABERTA,
        )
        db.add(cls)
        await db.flush()
        enrollment = Enrollment(
            tenant_id=alfa_id,
            student_id=alfa_student_sid,
            class_id=cls.id,
            price=99.90,
            status=EnrollmentStatus.CONCLUIDA,
        )
        db.add(enrollment)
        await db.commit()
        await db.refresh(enrollment)
        alfa_enrollment_id = enrollment.id

    sa_id = await _create_super_admin("sawrcr@wr.test", WR_TENANT_ID)
    token = _token(sa_id, "super_admin", WR_TENANT_ID)

    resp = await client.post(
        "/api/v1/certificates/",
        json={"enrollment_id": str(alfa_enrollment_id)},
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 404


# ─── SUPER_ADMIN in Alfa context ───

@pytest.mark.asyncio
async def test_super_admin_alfa_context_get_alfa_allowed(client):
    """SUPER_ADMIN in Alfa context GET Alfa cert → 200."""
    alfa_id = await _seed_alfa_tenant()
    _, alfa_student_sid = await _create_student(
        "saalfaget2@alfa.test", "SA Alfa Get2 Student", alfa_id
    )
    cert_id, _ = await _create_course_class_enrollment_cert(
        alfa_id, alfa_student_sid, "SA-ALFA-GET2-01", "SA Alfa Get2 Course"
    )

    sa_id = await _create_super_admin("saalfa@alfa.test", alfa_id)
    token = _token(sa_id, "super_admin", alfa_id)

    resp = await client.get(
        f"/api/v1/certificates/{cert_id}",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "alfa"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == str(cert_id)


@pytest.mark.asyncio
async def test_super_admin_alfa_context_get_wr_denied(client):
    """SUPER_ADMIN in Alfa context GET WR cert → 404."""
    alfa_id = await _seed_alfa_tenant()
    _, wr_student_sid = await _create_student(
        "sawrget4@wr.test", "SA WR Get4 Student", WR_TENANT_ID
    )
    wr_cert_id, _ = await _create_course_class_enrollment_cert(
        WR_TENANT_ID, wr_student_sid, "SA-WR-GET4-01", "SA WR Get4 Course"
    )

    sa_id = await _create_super_admin("saalfa2@alfa.test", alfa_id)
    token = _token(sa_id, "super_admin", alfa_id)

    resp = await client.get(
        f"/api/v1/certificates/{wr_cert_id}",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "alfa"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_super_admin_alfa_context_download_alfa_allowed(client):
    """SUPER_ADMIN in Alfa context download Alfa cert → 200."""
    alfa_id = await _seed_alfa_tenant()
    _, alfa_student_sid = await _create_student(
        "saalfadl2@alfa.test", "SA Alfa DL2 Student", alfa_id
    )
    cert_id, _ = await _create_course_class_enrollment_cert(
        alfa_id, alfa_student_sid, "SA-ALFA-DL2-01", "SA Alfa DL2 Course"
    )

    sa_id = await _create_super_admin("saalfa3@alfa.test", alfa_id)
    token = _token(sa_id, "super_admin", alfa_id)

    resp = await client.get(
        f"/api/v1/certificates/{cert_id}/download",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "alfa"},
    )
    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_super_admin_alfa_context_download_wr_denied(client):
    """SUPER_ADMIN in Alfa context download WR cert → 404."""
    alfa_id = await _seed_alfa_tenant()
    _, wr_student_sid = await _create_student(
        "sawrdl4@wr.test", "SA WR DL4 Student", WR_TENANT_ID
    )
    wr_cert_id, _ = await _create_course_class_enrollment_cert(
        WR_TENANT_ID, wr_student_sid, "SA-WR-DL4-01", "SA WR DL4 Course"
    )

    sa_id = await _create_super_admin("saalfa4@alfa.test", alfa_id)
    token = _token(sa_id, "super_admin", alfa_id)

    resp = await client.get(
        f"/api/v1/certificates/{wr_cert_id}/download",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "alfa"},
    )
    assert resp.status_code == 404


# ─── PDF branding ───

@pytest.mark.asyncio
async def test_wr_pdf_branding_correct(client):
    """WR certificate PDF contains WR identity."""
    _, wr_student_sid = await _create_student(
        "wrstupdf@wr.test", "WR PDF Student", WR_TENANT_ID
    )
    cert_id, _ = await _create_course_class_enrollment_cert(
        WR_TENANT_ID, wr_student_sid, "WR-PDF-01", "WR PDF Course"
    )

    wr_admin_id = await _create_admin("wrpdf@wr.test", WR_TENANT_ID)
    token = _token(wr_admin_id, "admin", WR_TENANT_ID)

    resp = await client.get(
        f"/api/v1/certificates/{cert_id}/download",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200
    # Extract text from PDF
    import io

    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(resp.content))
    text = " ".join(page.extract_text() or "" for page in reader.pages)
    assert "WR Consultoria" in text, "WR PDF must contain WR brand name"
    assert "Alfa Academy" not in text, "WR PDF must NOT contain Alfa brand"


@pytest.mark.asyncio
async def test_alfa_pdf_branding_correct(client):
    """Alfa certificate PDF contains Alfa Academy identity."""
    alfa_id = await _seed_alfa_tenant()
    _, alfa_student_sid = await _create_student(
        "alfastupdf@alfa.test", "Alfa PDF Student", alfa_id
    )
    cert_id, _ = await _create_course_class_enrollment_cert(
        alfa_id, alfa_student_sid, "ALFA-PDF-01", "Alfa PDF Course"
    )

    alfa_admin_id = await _create_admin("alfapdf@alfa.test", alfa_id)
    token = _token(alfa_admin_id, "admin", alfa_id)

    resp = await client.get(
        f"/api/v1/certificates/{cert_id}/download",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "alfa"},
    )
    assert resp.status_code == 200
    import io

    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(resp.content))
    text = " ".join(page.extract_text() or "" for page in reader.pages)
    assert "Alfa Academy" in text, "Alfa PDF must contain Alfa brand name"
    assert "WR Consultoria" not in text, "Alfa PDF must NOT contain WR brand"


# ─── Tenant-aware validation URL ───

@pytest.mark.asyncio
async def test_wr_validation_url_uses_wr_origin(client):
    """WR certificate validation URL points to WR frontend when Origin is trusted."""
    _, wr_student_sid = await _create_student(
        "wrstuurl@wr.test", "WR URL Student", WR_TENANT_ID
    )
    cert_id, _ = await _create_course_class_enrollment_cert(
        WR_TENANT_ID, wr_student_sid, "WR-URL-01", "WR URL Course"
    )

    wr_admin_id = await _create_admin("wrurl@wr.test", WR_TENANT_ID)
    token = _token(wr_admin_id, "admin", WR_TENANT_ID)

    # Set a trusted WR origin
    from app.core.config import settings
    original_trusted = settings.TRUSTED_FRONTEND_ORIGINS
    settings.TRUSTED_FRONTEND_ORIGINS = [
        "http://wr.test", "http://alfa.test"
    ]
    try:
        resp = await client.get(
            f"/api/v1/certificates/{cert_id}/download",
            headers={
                "Authorization": f"Bearer {token}",
                "x-tenant-slug": "wr",
                "origin": "http://wr.test",
            },
        )
        assert resp.status_code == 200
        import io

        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(resp.content))
        text = " ".join(page.extract_text() or "" for page in reader.pages)
        assert "http://wr.test/certificates/validate" in text, \
            "Validation URL should use WR origin"
    finally:
        settings.TRUSTED_FRONTEND_ORIGINS = original_trusted


@pytest.mark.asyncio
async def test_alfa_validation_url_uses_alfa_origin(client):
    """Alfa certificate validation URL points to Alfa frontend when Origin is trusted."""
    alfa_id = await _seed_alfa_tenant()
    _, alfa_student_sid = await _create_student(
        "alfastuurl@alfa.test", "Alfa URL Student", alfa_id
    )
    cert_id, _ = await _create_course_class_enrollment_cert(
        alfa_id, alfa_student_sid, "ALFA-URL-01", "Alfa URL Course"
    )

    alfa_admin_id = await _create_admin("alfaurl@alfa.test", alfa_id)
    token = _token(alfa_admin_id, "admin", alfa_id)

    from app.core.config import settings
    original_trusted = settings.TRUSTED_FRONTEND_ORIGINS
    settings.TRUSTED_FRONTEND_ORIGINS = [
        "http://wr.test", "http://alfa.test"
    ]
    try:
        resp = await client.get(
            f"/api/v1/certificates/{cert_id}/download",
            headers={
                "Authorization": f"Bearer {token}",
                "x-tenant-slug": "alfa",
                "origin": "http://alfa.test",
            },
        )
        assert resp.status_code == 200
        import io

        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(resp.content))
        text = " ".join(page.extract_text() or "" for page in reader.pages)
        assert "http://alfa.test/certificates/validate" in text, \
            "Validation URL should use Alfa origin"
        assert "http://wr.test" not in text, \
            "Alfa validation URL should NOT point to WR frontend"
    finally:
        settings.TRUSTED_FRONTEND_ORIGINS = original_trusted


@pytest.mark.asyncio
async def test_untrusted_origin_not_reflected(client):
    """Untrusted Origin must NOT be reflected in the validation URL (no open redirect)."""
    _, wr_student_sid = await _create_student(
        "wrstuuntr@wr.test", "WR Untr Student", WR_TENANT_ID
    )
    cert_id, _ = await _create_course_class_enrollment_cert(
        WR_TENANT_ID, wr_student_sid, "WR-UNTR-01", "WR Untr Course"
    )

    wr_admin_id = await _create_admin("wruntr@wr.test", WR_TENANT_ID)
    token = _token(wr_admin_id, "admin", WR_TENANT_ID)

    from app.core.config import settings
    original_trusted = settings.TRUSTED_FRONTEND_ORIGINS
    original_frontend = settings.FRONTEND_URL
    settings.TRUSTED_FRONTEND_ORIGINS = [
        "http://wr.test", "http://alfa.test"
    ]
    settings.FRONTEND_URL = "http://fallback.test"
    try:
        resp = await client.get(
            f"/api/v1/certificates/{cert_id}/download",
            headers={
                "Authorization": f"Bearer {token}",
                "x-tenant-slug": "wr",
                "origin": "http://evil.test",
            },
        )
        assert resp.status_code == 200
        import io

        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(resp.content))
        text = " ".join(page.extract_text() or "" for page in reader.pages)
        # Must use fallback FRONTEND_URL, NOT the untrusted origin
        assert "http://fallback.test/certificates/validate" in text, \
            "Untrusted Origin must fall back to FRONTEND_URL"
        assert "http://evil.test" not in text, \
            "Untrusted Origin must NOT be reflected in validation URL (open redirect)"
    finally:
        settings.TRUSTED_FRONTEND_ORIGINS = original_trusted
        settings.FRONTEND_URL = original_frontend
