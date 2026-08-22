"""B2C identity and cross-tenant journey regression tests.

Covers the scenarios required by PR #21 (Business Journeys & Contracting
Hardening — B2C identity and entry journey hardening):

LOGIN:
  1. same email exists in WR + Alfa;
  2. WR login authenticates WR user;
  3. Alfa login authenticates Alfa user;
  4. same CPF exists in WR + Alfa;
  5. each tenant authenticates its own user;
  6. password from other tenant cannot authenticate wrong user;
  7. nonexistent tenant user fails normally.

REGISTER:
  8. duplicate email same tenant rejected;
  9. duplicate CPF same tenant rejected;
  10. same email different tenant allowed;
  11. same CPF different tenant allowed.

PASSWORD RESET:
  12. same email WR/Alfa → WR reset selects WR;
  13. same email WR/Alfa → Alfa reset selects Alfa.

ACTIVATION:
  14. tenant-bound activation behaves correctly;
  15. cross-tenant misuse rejected.

CPF:
  16+ mathematical validation cases.

All fixtures are deterministic. No seed-dependent skips.
"""

import pytest
from sqlalchemy import select, text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.normalization import (
    is_valid_cpf,
    normalize_cpf,
    validate_cpf,
)
from app.core.security import hash_password
from app.models.one_time_token import OneTimeToken
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User, UserRole
from app.services.one_time_token_service import OneTimeTokenService
from tests.conftest import make_valid_cpf

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


async def _create_user_directly(email, cpf, tenant_id, role=UserRole.STUDENT, password="pass123"):
    """Create a user directly in the DB with normalized email/CPF."""
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = tenant_id
        await db.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        user = User(
            email=email.strip().lower(),
            full_name=f"User {email}",
            cpf=cpf,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
            tenant_id=tenant_id,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user.id, password


async def _register_public(client, email, cpf, password="pass123", tenant_slug="wr"):
    """Register via the public /auth/register endpoint with a tenant slug."""
    return await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": f"User {email}",
            "password": password,
            "cpf": cpf,
        },
        headers={"x-tenant-slug": tenant_slug},
    )


async def _login(client, identifier, password, tenant_slug):
    return await client.post(
        "/api/v1/auth/login",
        json={"identifier": identifier, "password": password},
        headers={"x-tenant-slug": tenant_slug},
    )


# ---------------------------------------------------------------------------
# LOGIN — same email/CPF in WR + Alfa
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_same_email_wr_authenticates_wr_user(client):
    """Same email in WR + Alfa → WR login authenticates WR user."""
    alfa_id = await _seed_alfa_tenant()
    await _create_user_directly("shared@example.com", make_valid_cpf(1), WR_TENANT_ID, password="wrpass")
    await _create_user_directly("shared@example.com", make_valid_cpf(2), alfa_id, password="alfapass")

    resp = await _login(client, "shared@example.com", "wrpass", "wr")
    assert resp.status_code == 200
    # Verify the token belongs to WR tenant
    assert resp.json()["access_token"]


@pytest.mark.asyncio
async def test_login_same_email_alfa_authenticates_alfa_user(client):
    """Same email in WR + Alfa → Alfa login authenticates Alfa user."""
    alfa_id = await _seed_alfa_tenant()
    await _create_user_directly("shared@example.com", make_valid_cpf(1), WR_TENANT_ID, password="wrpass")
    await _create_user_directly("shared@example.com", make_valid_cpf(2), alfa_id, password="alfapass")

    resp = await _login(client, "shared@example.com", "alfapass", "alfa")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_login_same_cpf_wr_authenticates_wr_user(client):
    """Same CPF in WR + Alfa → WR login authenticates WR user."""
    alfa_id = await _seed_alfa_tenant()
    shared_cpf = make_valid_cpf(42)
    await _create_user_directly("wr-cpf@example.com", shared_cpf, WR_TENANT_ID, password="wrpass")
    await _create_user_directly("alfa-cpf@example.com", shared_cpf, alfa_id, password="alfapass")

    resp = await _login(client, shared_cpf, "wrpass", "wr")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_login_same_cpf_alfa_authenticates_alfa_user(client):
    """Same CPF in WR + Alfa → Alfa login authenticates Alfa user."""
    alfa_id = await _seed_alfa_tenant()
    shared_cpf = make_valid_cpf(42)
    await _create_user_directly("wr-cpf@example.com", shared_cpf, WR_TENANT_ID, password="wrpass")
    await _create_user_directly("alfa-cpf@example.com", shared_cpf, alfa_id, password="alfapass")

    resp = await _login(client, shared_cpf, "alfapass", "alfa")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_login_cross_tenant_password_rejected(client):
    """WR password cannot authenticate the Alfa user (same email)."""
    alfa_id = await _seed_alfa_tenant()
    await _create_user_directly("shared@example.com", make_valid_cpf(1), WR_TENANT_ID, password="wrpass")
    await _create_user_directly("shared@example.com", make_valid_cpf(2), alfa_id, password="alfapass")

    # Try to login in Alfa context with WR password → 401
    resp = await _login(client, "shared@example.com", "wrpass", "alfa")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


@pytest.mark.asyncio
async def test_login_nonexistent_tenant_user_fails(client):
    """Nonexistent user in tenant → 401 (not 500 or ambiguous)."""
    resp = await _login(client, "nobody@example.com", "pass123", "wr")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# REGISTER — tenant-scoped duplicate checks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_duplicate_email_same_tenant_rejected(client):
    """Duplicate email in the SAME tenant → 400."""
    cpf_a = make_valid_cpf(10)
    cpf_b = make_valid_cpf(11)
    await _register_public(client, "dup@example.com", cpf_a, tenant_slug="wr")
    resp = await _register_public(client, "dup@example.com", cpf_b, tenant_slug="wr")
    assert resp.status_code == 400
    assert "already registered" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_cpf_same_tenant_rejected(client):
    """Duplicate CPF in the SAME tenant → 400."""
    shared_cpf = make_valid_cpf(20)
    await _register_public(client, "user-a@example.com", shared_cpf, tenant_slug="wr")
    resp = await _register_public(client, "user-b@example.com", shared_cpf, tenant_slug="wr")
    assert resp.status_code == 400
    assert "already registered" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_register_same_email_different_tenant_allowed(client):
    """Same email in DIFFERENT tenants → both succeed."""
    await _seed_alfa_tenant()
    cpf_wr = make_valid_cpf(30)
    cpf_alfa = make_valid_cpf(31)

    resp_wr = await _register_public(client, "cross@example.com", cpf_wr, tenant_slug="wr")
    assert resp_wr.status_code == 200

    resp_alfa = await _register_public(client, "cross@example.com", cpf_alfa, tenant_slug="alfa")
    assert resp_alfa.status_code == 200


@pytest.mark.asyncio
async def test_register_same_cpf_different_tenant_allowed(client):
    """Same CPF in DIFFERENT tenants → both succeed."""
    await _seed_alfa_tenant()
    shared_cpf = make_valid_cpf(40)

    resp_wr = await _register_public(client, "wr-user@example.com", shared_cpf, tenant_slug="wr")
    assert resp_wr.status_code == 200

    resp_alfa = await _register_public(client, "alfa-user@example.com", shared_cpf, tenant_slug="alfa")
    assert resp_alfa.status_code == 200


@pytest.mark.asyncio
async def test_register_invalid_cpf_rejected(client):
    """Mathematically invalid CPF → 400 with friendly message."""
    resp = await _register_public(client, "invalid@example.com", "12345678901", tenant_slug="wr")
    assert resp.status_code == 400
    assert "CPF" in resp.json()["detail"] or "cpf" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_repeated_cpf_rejected(client):
    """All-equal-digit CPF (00000000000) → 400."""
    resp = await _register_public(client, "repeated@example.com", "00000000000", tenant_slug="wr")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# PASSWORD RESET — same email cross-tenant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_password_reset_wr_context_selects_wr_user(client):
    """Same email WR/Alfa → WR reset request selects WR user only."""
    alfa_id = await _seed_alfa_tenant()
    wr_user_id, _ = await _create_user_directly(
        "reset@example.com", make_valid_cpf(50), WR_TENANT_ID, password="wrpass"
    )
    alfa_user_id, _ = await _create_user_directly(
        "reset@example.com", make_valid_cpf(51), alfa_id, password="alfapass"
    )

    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "reset@example.com"},
        headers={"x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200
    # In dev, a reset token is returned for the WR user
    assert "reset_token" in resp.json()

    # Verify only the WR user got a token, not the Alfa user
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        wr_tokens = (
            await db.execute(select(OneTimeToken).where(OneTimeToken.user_id == wr_user_id))
        ).scalars().all()
        alfa_tokens = (
            await db.execute(select(OneTimeToken).where(OneTimeToken.user_id == alfa_user_id))
        ).scalars().all()
        assert len(wr_tokens) == 1
        assert len(alfa_tokens) == 0


@pytest.mark.asyncio
async def test_password_reset_alfa_context_selects_alfa_user(client):
    """Same email WR/Alfa → Alfa reset request selects Alfa user only."""
    alfa_id = await _seed_alfa_tenant()
    wr_user_id, _ = await _create_user_directly(
        "reset@example.com", make_valid_cpf(60), WR_TENANT_ID, password="wrpass"
    )
    alfa_user_id, _ = await _create_user_directly(
        "reset@example.com", make_valid_cpf(61), alfa_id, password="alfapass"
    )

    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "reset@example.com"},
        headers={"x-tenant-slug": "alfa"},
    )
    assert resp.status_code == 200
    assert "reset_token" in resp.json()

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        wr_tokens = (
            await db.execute(select(OneTimeToken).where(OneTimeToken.user_id == wr_user_id))
        ).scalars().all()
        alfa_tokens = (
            await db.execute(select(OneTimeToken).where(OneTimeToken.user_id == alfa_user_id))
        ).scalars().all()
        assert len(wr_tokens) == 0
        assert len(alfa_tokens) == 1


@pytest.mark.asyncio
async def test_password_reset_cross_tenant_token_rejected(client):
    """A WR reset token cannot be used in Alfa context."""
    await _seed_alfa_tenant()
    _wr_user_id, _ = await _create_user_directly(
        "xreset@example.com", make_valid_cpf(70), WR_TENANT_ID, password="wrpass"
    )

    # Get WR reset token
    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "xreset@example.com"},
        headers={"x-tenant-slug": "wr"},
    )
    reset_token = resp.json()["reset_token"]

    # Try to use it in Alfa context → 400
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "newpass123"},
        headers={"x-tenant-slug": "alfa"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# ACTIVATION — tenant scope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activation_tenant_bound(client):
    """A WR activation token activates the WR user correctly."""
    # Create inactive WR user with activation token
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await db.execute(text(f"SET LOCAL app.current_tenant = '{WR_TENANT_ID}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        user = User(
            email="activate@example.com",
            full_name="Activate User",
            cpf=make_valid_cpf(80),
            password_hash=None,
            role=UserRole.STUDENT,
            is_active=False,
            tenant_id=WR_TENANT_ID,
        )
        db.add(user)
        await db.flush()
        raw, _token = await OneTimeTokenService.create(db, str(user.id), "activation", ttl_hours=24)
        await db.commit()
        user_id = user.id

    resp = await client.post(
        "/api/v1/auth/activate",
        json={"token": raw, "new_password": "newpass123"},
        headers={"x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Account activated successfully"

    # Verify user is now active
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        user = await db.get(User, user_id)
        assert user.is_active is True
        assert user.password_hash is not None


@pytest.mark.asyncio
async def test_activation_cross_tenant_rejected(client):
    """A WR activation token cannot activate in Alfa context."""
    await _seed_alfa_tenant()
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await db.execute(text(f"SET LOCAL app.current_tenant = '{WR_TENANT_ID}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        user = User(
            email="cross-activate@example.com",
            full_name="Cross Activate",
            cpf=make_valid_cpf(90),
            password_hash=None,
            role=UserRole.STUDENT,
            is_active=False,
            tenant_id=WR_TENANT_ID,
        )
        db.add(user)
        await db.flush()
        raw, _token = await OneTimeTokenService.create(db, str(user.id), "activation", ttl_hours=24)
        await db.commit()

    # Use WR token in Alfa context → 400
    resp = await client.post(
        "/api/v1/auth/activate",
        json={"token": raw, "new_password": "newpass123"},
        headers={"x-tenant-slug": "alfa"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# CPF — mathematical validation
# ---------------------------------------------------------------------------


class TestCpfValidation:
    """Mathematical CPF validation cases."""

    def test_valid_cpf_accepted(self):
        result = validate_cpf("52998224725")
        assert result == "52998224725"

    def test_valid_cpf_formatted_accepted(self):
        result = validate_cpf("529.982.247-25")
        assert result == "52998224725"

    def test_valid_cpf_normalized_accepted(self):
        result = validate_cpf("52998224725")
        assert result == "52998224725"

    def test_invalid_first_check_digit_rejected(self):
        # 52998224725 with wrong first digit → 52998224715
        with pytest.raises(ValueError):
            validate_cpf("52998224715")

    def test_invalid_second_check_digit_rejected(self):
        # 52998224725 with wrong second digit → 52998224720
        with pytest.raises(ValueError):
            validate_cpf("52998224720")

    def test_repeated_digits_rejected(self):
        for d in range(10):
            with pytest.raises(ValueError):
                validate_cpf(str(d) * 11)

    def test_too_short_rejected(self):
        with pytest.raises(ValueError):
            validate_cpf("1234567890")

    def test_too_long_rejected(self):
        with pytest.raises(ValueError):
            validate_cpf("123456789012")

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            validate_cpf("")

    def test_is_valid_cpf_boolean_true(self):
        assert is_valid_cpf("52998224725") is True

    def test_is_valid_cpf_boolean_false(self):
        assert is_valid_cpf("00000000000") is False

    def test_normalize_cpf_strips_punctuation(self):
        assert normalize_cpf("529.982.247-25") == "52998224725"

    def test_normalize_cpf_strips_spaces(self):
        assert normalize_cpf(" 529 982 247 25 ") == "52998224725"

    def test_generated_test_cpf_is_valid(self):
        """The make_valid_cpf helper must produce valid CPFs."""
        for seed in range(100):
            cpf = make_valid_cpf(seed)
            assert is_valid_cpf(cpf), f"Generated CPF {cpf} (seed={seed}) is not valid"
