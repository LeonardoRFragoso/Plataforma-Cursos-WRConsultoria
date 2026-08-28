"""Tests for identity security hardening: activation token exposure prevention,
email normalization consistency, and strict CPF format validation.

These tests verify the security contract:
- Production/staging HTTP responses must NOT expose raw activation tokens.
- Email normalization is consistent across all production identity writers.
- CPF format validation is strict (rejects arbitrary garbage).
- Cross-tenant identity assertions prove which tenant identity was selected.
"""


import pytest
from sqlalchemy import select, text

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User, UserRole
from app.services.one_time_token_service import OneTimeTokenService
from tests.conftest import make_valid_cnpj, make_valid_cpf

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_alfa_tenant():
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        alfa = Tenant(
            name="Alfa Academy",
            slug="alfa",
            status=TenantStatus.ACTIVE,
            contact_name="Alfa Admin",
            contact_email="admin@alfa.com",
            primary_color="#E86A17",
        )
        db.add(alfa)
        await db.commit()
        await db.refresh(alfa)
        return alfa.id


# ---------------------------------------------------------------------------
# Activation token exposure — production contract
# ---------------------------------------------------------------------------


class TestActivationTokenExposure:
    """Production/staging HTTP responses must NOT expose raw activation tokens."""

    @pytest.mark.asyncio
    async def test_employee_create_response_no_token_in_production(
        self, client, admin_headers, monkeypatch
    ):
        """Employee creation in production must NOT return activation_token."""
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")

        # Create a company first
        company_resp = await client.post(
            "/api/v1/companies/",
            json={
                "legal_name": "Test Company LTDA",
                "trade_name": "TestCo",
                "cnpj": make_valid_cnpj(1),
                "rh_name": "RH",
                "rh_email": "rh@test.com",
                "rh_phone": "(11) 99999-9999",
                "address": "Rua Test, 123",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01000-000",
            },
            headers=admin_headers,
        )
        assert company_resp.status_code == 201
        company_id = company_resp.json()["id"]

        cpf = make_valid_cpf(99)
        resp = await client.post(
            f"/api/v1/companies/{company_id}/employees",
            json={
                "full_name": "Employee Test",
                "cpf": cpf,
                "email": f"emp_{cpf[:6]}@test.com",
                "phone": "(11) 99999-9999",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        # Production contract: NO raw activation token
        assert data.get("activation_token") is None

    @pytest.mark.asyncio
    async def test_csv_import_response_no_tokens_in_production(
        self, client, admin_headers, monkeypatch
    ):
        """CSV import in production must NOT return activation_tokens array."""
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")

        company_resp = await client.post(
            "/api/v1/companies/",
            json={
                "legal_name": "CSV Company LTDA",
                "trade_name": "CSVCo",
                "cnpj": make_valid_cnpj(2),
                "rh_name": "RH",
                "rh_email": "rh2@test.com",
                "rh_phone": "(11) 99999-9999",
                "address": "Rua Test, 456",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01000-000",
            },
            headers=admin_headers,
        )
        assert company_resp.status_code == 201
        company_id = company_resp.json()["id"]

        csv_content = "full_name,cpf,email,phone\n"
        for i in range(3):
            csv_content += f"Func {i},{make_valid_cpf(100 + i)},func{i}_{hash('csvtest' + str(i)) % 100000:05d}@test.com,11999999999\n"

        files = {"file": ("employees.csv", csv_content.encode("utf-8"), "text/csv")}
        resp = await client.post(
            f"/api/v1/companies/{company_id}/employees/import",
            files=files,
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # Production contract: NO activation_tokens in response
        assert "activation_tokens" not in data

    @pytest.mark.asyncio
    async def test_partner_approval_no_token_in_production(
        self, client, super_admin_headers, monkeypatch
    ):
        """Partner lead approval in production must NOT return activation_token."""
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")

        # Create a partner lead
        lead_resp = await client.post(
            "/api/v1/partner-leads",
            json={
                "company_name": "Partner Test Corp",
                "cnpj": "12345678000199",
                "contact_name": "Partner Admin",
                "contact_email": f"partner_{hash('ptest') % 100000:05d}@test.com",
                "contact_phone": "(11) 99999-9999",
                "message": "Interested in partnership",
            },
        )
        assert lead_resp.status_code == 201
        lead_id = lead_resp.json()["id"]

        # Approve the lead
        resp = await client.post(
            f"/api/v1/partner-leads/{lead_id}/approve",
            headers=super_admin_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # Production contract: NO raw activation token
        assert data.get("activation_token") is None
        # Should still return tenant_id and admin_user_id
        assert "tenant_id" in data
        assert "admin_user_id" in data

    @pytest.mark.asyncio
    async def test_employee_create_response_has_token_in_dev(
        self, client, admin_headers, monkeypatch
    ):
        """Employee creation in dev/test MAY return activation_token for tests."""
        monkeypatch.setattr(settings, "ENVIRONMENT", "development")

        company_resp = await client.post(
            "/api/v1/companies/",
            json={
                "legal_name": "Dev Company LTDA",
                "trade_name": "DevCo",
                "cnpj": make_valid_cnpj(3),
                "rh_name": "RH",
                "rh_email": "rh3@test.com",
                "rh_phone": "(11) 99999-9999",
                "address": "Rua Test, 789",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01000-000",
            },
            headers=admin_headers,
        )
        assert company_resp.status_code == 201
        company_id = company_resp.json()["id"]

        cpf = make_valid_cpf(50)
        resp = await client.post(
            f"/api/v1/companies/{company_id}/employees",
            json={
                "full_name": "Dev Employee",
                "cpf": cpf,
                "email": f"devemp_{cpf[:6]}@test.com",
                "phone": "(11) 99999-9999",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        # Dev/test: token is returned for automated tests
        assert data.get("activation_token") is not None


# ---------------------------------------------------------------------------
# Email normalization — consistency across all production identity writers
# ---------------------------------------------------------------------------


class TestEmailNormalization:
    """Email normalization must be consistent across all identity paths."""

    @pytest.mark.asyncio
    async def test_registration_normalizes_mixed_case_email(self, client):
        """Registration with User@Test.com stores user@test.com."""
        email = f"User{hash('mixed1') % 100000:05d}@Test.COM"
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "full_name": "Mixed Case User",
                "password": "pass123",
                "cpf": make_valid_cpf(10),
            },
        )
        assert resp.status_code == 200, resp.text
        # Verify stored email is lowercase
        async with AsyncSessionLocal() as db:
            await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
            stmt = select(User).where(User.email == email.strip().lower())
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            assert user is not None
            assert user.email == email.strip().lower()

    @pytest.mark.asyncio
    async def test_login_with_case_variation_succeeds(self, client):
        """Login with USER@Test.com succeeds for user@test.com."""
        email_lower = f"caseuser{hash('mixed2') % 100000:05d}@test.com"
        # Register with lowercase
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email_lower,
                "full_name": "Case User",
                "password": "pass123",
                "cpf": make_valid_cpf(20),
            },
        )
        assert resp.status_code == 200

        # Login with uppercase variant
        upper_email = email_lower.upper()
        resp = await client.post(
            "/api/v1/auth/login",
            json={"identifier": upper_email, "password": "pass123"},
        )
        assert resp.status_code == 200, resp.text
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_login_with_surrounding_whitespace_stripped(self, client):
        """Login with surrounding whitespace is stripped by normalizer."""
        email = f"spaceuser{hash('mixed3') % 100000:05d}@test.com"
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "full_name": "Space User",
                "password": "pass123",
                "cpf": make_valid_cpf(30),
            },
        )
        assert resp.status_code == 200

        # Login with surrounding whitespace
        resp = await client.post(
            "/api/v1/auth/login",
            json={"identifier": f"  {email}  ", "password": "pass123"},
        )
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_forgot_password_case_variation_selects_same_user(self, client):
        """Forgot-password with case variation selects the same tenant user."""
        email = f"forgot{hash('mixed4') % 100000:05d}@test.com"
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "full_name": "Forgot User",
                "password": "pass123",
                "cpf": make_valid_cpf(40),
            },
        )
        assert resp.status_code == 200

        # Request reset with uppercase variant
        resp = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": email.upper()},
        )
        assert resp.status_code == 200
        # In dev/test, reset_token is returned
        data = resp.json()
        if "reset_token" in data:
            # Verify the token belongs to the correct user
            async with AsyncSessionLocal() as db:
                await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
                token = await OneTimeTokenService.consume(db, data["reset_token"], "reset")
                assert token is not None
                stmt = select(User).where(User.id == token.user_id)
                result = await db.execute(stmt)
                user = result.scalar_one_or_none()
                assert user is not None
                assert user.email == email  # stored lowercase

    @pytest.mark.asyncio
    async def test_corporate_employee_email_normalized(self, client, admin_headers):
        """Corporate employee creation normalizes email."""
        company_resp = await client.post(
            "/api/v1/companies/",
            json={
                "legal_name": "Norm Company LTDA",
                "trade_name": "NormCo",
                "cnpj": make_valid_cnpj(4),
                "rh_name": "RH",
                "rh_email": "rh@norm.com",
                "rh_phone": "(11) 99999-9999",
                "address": "Rua Norm, 123",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01000-000",
            },
            headers=admin_headers,
        )
        company_id = company_resp.json()["id"]

        mixed_email = f"Employee{hash('norm2') % 100000:05d}@Company.COM"
        resp = await client.post(
            f"/api/v1/companies/{company_id}/employees",
            json={
                "full_name": "Norm Employee",
                "cpf": make_valid_cpf(60),
                "email": mixed_email,
                "phone": "(11) 99999-9999",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text

        # Verify stored email is lowercase
        async with AsyncSessionLocal() as db:
            await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
            stmt = select(User).where(User.email == mixed_email.strip().lower())
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            assert user is not None
            assert user.email == mixed_email.strip().lower()

    @pytest.mark.asyncio
    async def test_csv_employee_email_normalized(self, client, admin_headers):
        """CSV employee import normalizes email."""
        company_resp = await client.post(
            "/api/v1/companies/",
            json={
                "legal_name": "CSV Norm Company LTDA",
                "trade_name": "CSVNormCo",
                "cnpj": make_valid_cnpj(5),
                "rh_name": "RH",
                "rh_email": "rh3@norm.com",
                "rh_phone": "(11) 99999-9999",
                "address": "Rua Norm, 456",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01000-000",
            },
            headers=admin_headers,
        )
        company_id = company_resp.json()["id"]

        mixed_email = f"CSV{hash('norm4') % 100000:05d}@Email.COM"
        csv_content = f"full_name,cpf,email,phone\nCSV User,{make_valid_cpf(70)},{mixed_email},11999999999\n"
        files = {"file": ("employees.csv", csv_content.encode("utf-8"), "text/csv")}
        resp = await client.post(
            f"/api/v1/companies/{company_id}/employees/import",
            files=files,
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["created"] == 1

        # Verify stored email is lowercase
        async with AsyncSessionLocal() as db:
            await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
            stmt = select(User).where(User.email == mixed_email.strip().lower())
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            assert user is not None
            assert user.email == mixed_email.strip().lower()

    @pytest.mark.asyncio
    async def test_partner_admin_email_normalized(self, client, super_admin_headers):
        """Partner admin creation normalizes email."""
        mixed_email = f"Partner{hash('norm5') % 100000:05d}@Admin.COM"
        lead_resp = await client.post(
            "/api/v1/partner-leads",
            json={
                "company_name": "Partner Norm Corp",
                "cnpj": make_valid_cnpj(6),
                "contact_name": "Partner Admin",
                "contact_email": mixed_email,
                "contact_phone": "(11) 99999-9999",
            },
        )
        assert lead_resp.status_code == 201
        lead_id = lead_resp.json()["id"]

        resp = await client.post(
            f"/api/v1/partner-leads/{lead_id}/approve",
            headers=super_admin_headers,
        )
        assert resp.status_code == 200, resp.text

        # Verify stored email is lowercase
        async with AsyncSessionLocal() as db:
            await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
            stmt = select(User).where(User.email == mixed_email.strip().lower())
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            assert user is not None
            assert user.email == mixed_email.strip().lower()

    @pytest.mark.asyncio
    async def test_same_normalized_email_same_tenant_rejected(self, client):
        """Same normalized email in the same tenant is rejected."""
        email = f"dup{hash('norm7') % 100000:05d}@test.com"
        # First registration succeeds
        resp1 = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "full_name": "First User",
                "password": "pass123",
                "cpf": make_valid_cpf(80),
            },
        )
        assert resp1.status_code == 200

        # Second registration with case variant should fail (same normalized email)
        resp2 = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email.upper(),
                "full_name": "Second User",
                "password": "pass456",
                "cpf": make_valid_cpf(81),
            },
        )
        assert resp2.status_code == 400
        assert "already registered" in resp2.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_same_normalized_email_cross_tenant_allowed(self, client):
        """Same normalized email in different tenants is allowed."""
        alfa_id = await _seed_alfa_tenant()
        email = f"cross{hash('norm8') % 100000:05d}@test.com"

        # Register in WR
        resp1 = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "full_name": "WR User",
                "password": "pass123",
                "cpf": make_valid_cpf(90),
            },
        )
        assert resp1.status_code == 200

        # Register same email in Alfa (directly in DB since no Alfa frontend context)
        async with AsyncSessionLocal() as db:
            db.info["tenant_id"] = alfa_id
            await db.execute(text(f"SET LOCAL app.current_tenant = '{alfa_id}'"))
            await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
            from app.models.student import Student

            user = User(
                tenant_id=alfa_id,
                email=email,
                cpf=make_valid_cpf(91),
                full_name="Alfa User",
                password_hash=hash_password("pass123"),
                role=UserRole.STUDENT,
            )
            db.add(user)
            await db.flush()
            student = Student(
                tenant_id=alfa_id,
                user_id=user.id,
                cpf=make_valid_cpf(91),
            )
            db.add(student)
            await db.commit()
            assert user.email == email  # both stored as lowercase


# ---------------------------------------------------------------------------
# Cross-tenant identity assertions — prove which tenant identity was selected
# ---------------------------------------------------------------------------


class TestCrossTenantIdentityAssertions:
    """Strengthen cross-tenant tests to prove which identity was authenticated."""

    @pytest.mark.asyncio
    async def test_same_email_wr_login_identifies_wr_user(self, client):
        """WR login with same email authenticates WR user, not Alfa user."""
        alfa_id = await _seed_alfa_tenant()
        email = f"assert{hash('cross1') % 100000:05d}@test.com"

        # Create WR user
        wr_resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "full_name": "WR Identity User",
                "password": "wrpass123",
                "cpf": make_valid_cpf(110),
            },
        )
        assert wr_resp.status_code == 200
        wr_user_id = wr_resp.json()["id"]

        # Create Alfa user with same email
        async with AsyncSessionLocal() as db:
            db.info["tenant_id"] = alfa_id
            await db.execute(text(f"SET LOCAL app.current_tenant = '{alfa_id}'"))
            await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
            from app.models.student import Student

            alfa_user = User(
                tenant_id=alfa_id,
                email=email,
                cpf=make_valid_cpf(111),
                full_name="Alfa Identity User",
                password_hash=hash_password("alfapass123"),
                role=UserRole.STUDENT,
            )
            db.add(alfa_user)
            await db.flush()
            student = Student(tenant_id=alfa_id, user_id=alfa_user.id, cpf=make_valid_cpf(111))
            db.add(student)
            await db.commit()
            alfa_user_id = str(alfa_user.id)

        # Login via WR context (default tenant in tests)
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"identifier": email, "password": "wrpass123"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        # Verify /auth/me identifies the WR user, NOT the Alfa user
        me_resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["id"] == wr_user_id
        assert me_data["full_name"] == "WR Identity User"
        # The Alfa user must NOT be the authenticated identity
        assert me_data["id"] != alfa_user_id
        assert me_data["full_name"] != "Alfa Identity User"

    @pytest.mark.asyncio
    async def test_same_cpf_wr_login_identifies_wr_user(self, client):
        """WR login with same CPF authenticates WR user, not Alfa user."""
        alfa_id = await _seed_alfa_tenant()
        cpf = make_valid_cpf(120)

        # Create WR user with this CPF
        wr_resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"wr_cpf{hash('cross2') % 100000:05d}@test.com",
                "full_name": "WR CPF User",
                "password": "wrpass123",
                "cpf": cpf,
            },
        )
        assert wr_resp.status_code == 200
        wr_user_id = wr_resp.json()["id"]

        # Create Alfa user with same CPF
        async with AsyncSessionLocal() as db:
            db.info["tenant_id"] = alfa_id
            await db.execute(text(f"SET LOCAL app.current_tenant = '{alfa_id}'"))
            await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
            from app.models.student import Student

            alfa_user = User(
                tenant_id=alfa_id,
                email=f"alfa_cpf{hash('cross3') % 100000:05d}@test.com",
                cpf=cpf,
                full_name="Alfa CPF User",
                password_hash=hash_password("alfapass123"),
                role=UserRole.STUDENT,
            )
            db.add(alfa_user)
            await db.flush()
            student = Student(tenant_id=alfa_id, user_id=alfa_user.id, cpf=cpf)
            db.add(student)
            await db.commit()
            alfa_user_id = str(alfa_user.id)

        # Login via WR context using CPF
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"identifier": cpf, "password": "wrpass123"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        # Verify /auth/me identifies the WR user, NOT the Alfa user
        me_resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["id"] == wr_user_id
        assert me_data["full_name"] == "WR CPF User"
        assert me_data["id"] != alfa_user_id


# ---------------------------------------------------------------------------
# Login CPF classification — arbitrary 11-digit strings not CPF
# ---------------------------------------------------------------------------


class TestLoginCpfClassification:
    """Login must not classify arbitrary 11-digit-containing strings as CPF."""

    @pytest.mark.asyncio
    async def test_arbitrary_string_with_11_digits_not_cpf(self, client):
        """abc52998224725xyz should not be classified as CPF for login."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={"identifier": "abc52998224725xyz", "password": "anypass"},
        )
        # Should be rejected as invalid identifier, not treated as CPF
        assert resp.status_code == 400
        assert "valid CPF" in resp.json()["detail"] or "Identifier" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_cpf_with_slashes_not_accepted(self, client):
        """529/982/247-25 should not be classified as CPF."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={"identifier": "529/982/247-25", "password": "anypass"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_valid_11_digit_cpf_accepted_for_login(self, client):
        """A valid 11-digit CPF should be accepted for login classification."""
        cpf = make_valid_cpf(130)
        # Register a user with this CPF
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"cpfinvalid{hash('cross4') % 100000:05d}@test.com",
                "full_name": "CPF Test User",
                "password": "pass123",
                "cpf": cpf,
            },
        )
        assert resp.status_code == 200

        # Login with CPF should work
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"identifier": cpf, "password": "pass123"},
        )
        assert login_resp.status_code == 200

    @pytest.mark.asyncio
    async def test_formatted_cpf_accepted_for_login(self, client):
        """A formatted CPF (DDD.DDD.DDD-DD) should be accepted for login."""
        cpf = make_valid_cpf(140)
        formatted = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:11]}"
        # Register
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"fmtcpf{hash('cross5') % 100000:05d}@test.com",
                "full_name": "Formatted CPF User",
                "password": "pass123",
                "cpf": cpf,
            },
        )
        assert resp.status_code == 200

        # Login with formatted CPF
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"identifier": formatted, "password": "pass123"},
        )
        assert login_resp.status_code == 200
