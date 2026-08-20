"""Authentication security hardening tests.

Covers:
- Forgot-password token exposure (dev vs staging vs production)
- Login tenant isolation (cross-tenant rejected)
- SUPER_ADMIN login contract (WR only)
- Reset-password tenant isolation
- Refresh token tenant isolation
- Auth/me tenant isolation
- One-time token security properties
- Demo seed password sync
"""

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.one_time_token import OneTimeToken
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User, UserRole
from app.services.one_time_token_service import OneTimeTokenService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_alfa_tenant():
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        from sqlalchemy import text

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


async def _create_user(email, tenant_id, role=UserRole.ADMIN, password="pass123"):
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = tenant_id
        from sqlalchemy import text

        await db.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        user = User(
            email=email,
            full_name=f"User {email}",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password(password),
            role=role,
            is_active=True,
            tenant_id=tenant_id,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user.id, password


async def _login(client, email, password, tenant_slug):
    """Login with a specific tenant slug header."""
    return await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": password},
        headers={"x-tenant-slug": tenant_slug},
    )


# ---------------------------------------------------------------------------
# FORGOT PASSWORD — token exposure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forgot_password_dev_returns_reset_token(client):
    """In development, forgot-password returns the raw reset token."""
    _user_id, _ = await _create_user("dev-reset@example.com", WR_TENANT_ID)
    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "dev-reset@example.com"},
        headers={"x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200
    assert "reset_token" in resp.json()


@pytest.mark.asyncio
async def test_forgot_password_staging_no_reset_token(client):
    """In staging, forgot-password must NOT return a reset token."""
    _user_id, _ = await _create_user("staging-reset@example.com", WR_TENANT_ID)
    # Patch only the auth module's env check, not the global settings,
    # so the TenantResolver middleware still operates in development mode.
    with patch("app.api.routes.auth._current_env", return_value="staging"):
        resp = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "staging-reset@example.com"},
            headers={"x-tenant-slug": "wr"},
        )
    assert resp.status_code == 200
    assert "reset_token" not in resp.json()
    assert resp.json() == {"detail": "If the email exists, a reset link was sent"}


@pytest.mark.asyncio
async def test_forgot_password_production_no_reset_token(client):
    """In production, forgot-password must NOT return a reset token."""
    _user_id, _ = await _create_user("prod-reset@example.com", WR_TENANT_ID)
    with patch("app.api.routes.auth._current_env", return_value="production"):
        resp = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "prod-reset@example.com"},
            headers={"x-tenant-slug": "wr"},
        )
    assert resp.status_code == 200
    assert "reset_token" not in resp.json()
    assert resp.json() == {"detail": "If the email exists, a reset link was sent"}


@pytest.mark.asyncio
async def test_forgot_password_unknown_email_generic_response(client):
    """Unknown email returns the same generic response (no enumeration)."""
    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nonexistent@example.com"},
        headers={"x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200
    # In dev, unknown user still returns generic (no reset_token)
    assert "reset_token" not in resp.json()
    assert resp.json() == {"detail": "If the email exists, a reset link was sent"}


@pytest.mark.asyncio
async def test_forgot_password_staging_unknown_same_as_existing(client):
    """In staging, existing and unknown emails return identical responses."""
    _user_id, _ = await _create_user("staging-cmp@example.com", WR_TENANT_ID)
    with patch("app.api.routes.auth._current_env", return_value="staging"):
        resp_existing = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "staging-cmp@example.com"},
            headers={"x-tenant-slug": "wr"},
        )
        resp_unknown = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nonexistent-cmp@example.com"},
            headers={"x-tenant-slug": "wr"},
        )
    assert resp_existing.json() == resp_unknown.json()


# ---------------------------------------------------------------------------
# FORGOT PASSWORD — tenant boundary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forgot_password_wr_context_no_alfa_token(client):
    """WR context + Alfa email → generic response, no Alfa reset token created."""
    alfa_id = await _seed_alfa_tenant()
    alfa_user_id, _ = await _create_user("alfa-fp@alfa.com", alfa_id)

    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "alfa-fp@alfa.com"},
        headers={"x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200
    # In dev, a WR-context request for an Alfa user should NOT create a token
    # and should return the generic response (no reset_token).
    assert "reset_token" not in resp.json()

    # Verify no token was created for the Alfa user
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text

        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        result = await db.execute(
            select(OneTimeToken).where(OneTimeToken.user_id == alfa_user_id)
        )
        tokens = result.scalars().all()
        assert len(tokens) == 0, "No reset token should be created for cross-tenant user"


@pytest.mark.asyncio
async def test_forgot_password_alfa_context_no_wr_token(client):
    """Alfa context + WR email → generic response, no WR reset token created."""
    wr_user_id, _ = await _create_user("wr-fp@wr.com", WR_TENANT_ID)
    await _seed_alfa_tenant()

    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "wr-fp@wr.com"},
        headers={"x-tenant-slug": "alfa"},
    )
    assert resp.status_code == 200
    assert "reset_token" not in resp.json()

    async with AsyncSessionLocal() as db:
        from sqlalchemy import text

        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        result = await db.execute(
            select(OneTimeToken).where(OneTimeToken.user_id == wr_user_id)
        )
        tokens = result.scalars().all()
        assert len(tokens) == 0, "No reset token should be created for cross-tenant user"


# ---------------------------------------------------------------------------
# LOGIN — tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_wr_admin_in_wr(client):
    """WR admin + WR context → 200."""
    await _create_user("wradmin@wr.com", WR_TENANT_ID, role=UserRole.ADMIN, password="pass123")
    resp = await _login(client, "wradmin@wr.com", "pass123", "wr")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_login_alfa_admin_in_alfa(client):
    """Alfa admin + Alfa context → 200."""
    alfa_id = await _seed_alfa_tenant()
    await _create_user("alfaadmin@alfa.com", alfa_id, role=UserRole.ADMIN, password="pass123")
    resp = await _login(client, "alfaadmin@alfa.com", "pass123", "alfa")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_login_wr_student_in_wr(client):
    """WR student + WR context → 200."""
    await _create_user("wrstudent@wr.com", WR_TENANT_ID, role=UserRole.STUDENT, password="pass123")
    resp = await _login(client, "wrstudent@wr.com", "pass123", "wr")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_login_alfa_student_in_alfa(client):
    """Alfa student + Alfa context → 200."""
    alfa_id = await _seed_alfa_tenant()
    await _create_user("alfastudent@alfa.com", alfa_id, role=UserRole.STUDENT, password="pass123")
    resp = await _login(client, "alfastudent@alfa.com", "pass123", "alfa")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_login_alfa_admin_in_wr_rejected(client):
    """Alfa admin + WR context → 401 (cross-tenant rejected)."""
    alfa_id = await _seed_alfa_tenant()
    await _create_user("crossalfa@alfa.com", alfa_id, role=UserRole.ADMIN, password="pass123")
    resp = await _login(client, "crossalfa@alfa.com", "pass123", "wr")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


@pytest.mark.asyncio
async def test_login_wr_admin_in_alfa_rejected(client):
    """WR admin + Alfa context → 401 (cross-tenant rejected)."""
    await _create_user("crosswr@wr.com", WR_TENANT_ID, role=UserRole.ADMIN, password="pass123")
    await _seed_alfa_tenant()
    resp = await _login(client, "crosswr@wr.com", "pass123", "alfa")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


@pytest.mark.asyncio
async def test_login_alfa_student_in_wr_rejected(client):
    """Alfa student + WR context → 401."""
    alfa_id = await _seed_alfa_tenant()
    await _create_user("crossalfastu@alfa.com", alfa_id, role=UserRole.STUDENT, password="pass123")
    resp = await _login(client, "crossalfastu@alfa.com", "pass123", "wr")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_wr_student_in_alfa_rejected(client):
    """WR student + Alfa context → 401."""
    await _create_user("crosswrstu@wr.com", WR_TENANT_ID, role=UserRole.STUDENT, password="pass123")
    await _seed_alfa_tenant()
    resp = await _login(client, "crosswrstu@wr.com", "pass123", "alfa")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# LOGIN — SUPER_ADMIN contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_super_admin_in_wr(client):
    """SUPER_ADMIN + WR context → 200."""
    await _create_user(
        "super@wr.com", WR_TENANT_ID, role=UserRole.SUPER_ADMIN, password="super123"
    )
    resp = await _login(client, "super@wr.com", "super123", "wr")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_login_super_admin_in_alfa_rejected(client):
    """SUPER_ADMIN + Alfa context → 401 (SUPER_ADMIN bound to WR only)."""
    await _create_user(
        "supercross@wr.com", WR_TENANT_ID, role=UserRole.SUPER_ADMIN, password="super123"
    )
    await _seed_alfa_tenant()
    resp = await _login(client, "supercross@wr.com", "super123", "alfa")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


# ---------------------------------------------------------------------------
# RESET PASSWORD — tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_password_same_tenant(client):
    """Valid same-tenant reset → 200."""
    _user_id, _ = await _create_user("reset-ok@wr.com", WR_TENANT_ID, password="oldpass")
    # Get reset token in WR context
    forgot = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "reset-ok@wr.com"},
        headers={"x-tenant-slug": "wr"},
    )
    assert "reset_token" in forgot.json()
    reset_token = forgot.json()["reset_token"]

    # Reset in WR context
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "newpass123"},
        headers={"x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200

    # Login with new password
    login = await _login(client, "reset-ok@wr.com", "newpass123", "wr")
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_cross_tenant_rejected(client):
    """Cross-tenant reset → 400 (token obtained in WR, used in Alfa context)."""
    _user_id, _ = await _create_user("reset-cross@wr.com", WR_TENANT_ID, password="oldpass")
    await _seed_alfa_tenant()

    # Get reset token in WR context
    forgot = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "reset-cross@wr.com"},
        headers={"x-tenant-slug": "wr"},
    )
    reset_token = forgot.json()["reset_token"]

    # Try to reset in Alfa context → rejected
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "newpass123"},
        headers={"x-tenant-slug": "alfa"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_token_reuse_rejected(client):
    """Consumed token cannot be reused."""
    _user_id, _ = await _create_user("reset-reuse@wr.com", WR_TENANT_ID, password="oldpass")
    forgot = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "reset-reuse@wr.com"},
        headers={"x-tenant-slug": "wr"},
    )
    reset_token = forgot.json()["reset_token"]

    first = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "newpass123"},
        headers={"x-tenant-slug": "wr"},
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "another123"},
        headers={"x-tenant-slug": "wr"},
    )
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_reset_token_wrong_purpose_rejected(client):
    """Token with wrong purpose is rejected."""
    user_id, _ = await _create_user("reset-purpose@wr.com", WR_TENANT_ID, password="oldpass")
    # Create an activation token
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text

        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        raw, _ = await OneTimeTokenService.create(db, str(user_id), "activation")
        await db.commit()

    # Try to use activation token for reset
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "new_password": "newpass123"},
        headers={"x-tenant-slug": "wr"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# REFRESH TOKEN — tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_wr_token_in_wr(client):
    """WR refresh token + WR context → 200."""
    await _create_user("refresh-wr@wr.com", WR_TENANT_ID, password="pass123")
    login = await _login(client, "refresh-wr@wr.com", "pass123", "wr")
    refresh_tok = login.json()["refresh_token"]

    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_tok},
        headers={"x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_refresh_wr_token_in_alfa_rejected(client):
    """WR refresh token + Alfa context → 401."""
    await _create_user("refresh-cross@wr.com", WR_TENANT_ID, password="pass123")
    await _seed_alfa_tenant()
    login = await _login(client, "refresh-cross@wr.com", "pass123", "wr")
    refresh_tok = login.json()["refresh_token"]

    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_tok},
        headers={"x-tenant-slug": "alfa"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_alfa_token_in_alfa(client):
    """Alfa refresh token + Alfa context → 200."""
    alfa_id = await _seed_alfa_tenant()
    await _create_user("refresh-alfa@alfa.com", alfa_id, password="pass123")
    login = await _login(client, "refresh-alfa@alfa.com", "pass123", "alfa")
    refresh_tok = login.json()["refresh_token"]

    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_tok},
        headers={"x-tenant-slug": "alfa"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_refresh_alfa_token_in_wr_rejected(client):
    """Alfa refresh token + WR context → 401."""
    alfa_id = await _seed_alfa_tenant()
    await _create_user("refresh-alfa-wr@alfa.com", alfa_id, password="pass123")
    login = await _login(client, "refresh-alfa-wr@alfa.com", "pass123", "alfa")
    refresh_tok = login.json()["refresh_token"]

    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_tok},
        headers={"x-tenant-slug": "wr"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# AUTH /ME — tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_me_wr_token_in_wr(client):
    """WR token + WR context → 200."""
    await _create_user("me-wr@wr.com", WR_TENANT_ID, password="pass123")
    login = await _login(client, "me-wr@wr.com", "pass123", "wr")
    token = login.json()["access_token"]

    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_auth_me_wr_token_in_alfa_rejected(client):
    """WR token + Alfa context → 403/401."""
    await _create_user("me-cross@wr.com", WR_TENANT_ID, password="pass123")
    await _seed_alfa_tenant()
    login = await _login(client, "me-cross@wr.com", "pass123", "wr")
    token = login.json()["access_token"]

    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "alfa"},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_auth_me_alfa_token_in_alfa(client):
    """Alfa token + Alfa context → 200."""
    alfa_id = await _seed_alfa_tenant()
    await _create_user("me-alfa@alfa.com", alfa_id, password="pass123")
    login = await _login(client, "me-alfa@alfa.com", "pass123", "alfa")
    token = login.json()["access_token"]

    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "alfa"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_auth_me_alfa_token_in_wr_rejected(client):
    """Alfa token + WR context → 403/401."""
    alfa_id = await _seed_alfa_tenant()
    await _create_user("me-alfa-wr@alfa.com", alfa_id, password="pass123")
    login = await _login(client, "me-alfa-wr@alfa.com", "pass123", "alfa")
    token = login.json()["access_token"]

    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# ONE-TIME TOKEN — security properties
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_one_time_token_hashed():
    """Token hash is stored, not the raw token."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text

        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        user = User(
            email=f"tok-hash-{uuid.uuid4().hex[:6]}@example.com",
            full_name="Token Hash Test",
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(user)
        await db.flush()
        raw, token = await OneTimeTokenService.create(db, str(user.id), "reset")
        await db.commit()

        # The stored hash must NOT equal the raw token
        assert token.token_hash != raw
        # The hash must be a SHA-256 hex digest (64 chars)
        assert len(token.token_hash) == 64


@pytest.mark.asyncio
async def test_one_time_token_single_use():
    """Consumed token cannot be reused."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text

        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        user = User(
            email=f"tok-single-{uuid.uuid4().hex[:6]}@example.com",
            full_name="Token Single Test",
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(user)
        await db.flush()
        raw, _ = await OneTimeTokenService.create(db, str(user.id), "reset")
        await db.commit()

    async with AsyncSessionLocal() as db:
        consumed = await OneTimeTokenService.consume(db, raw, "reset")
        assert consumed is not None
        assert consumed.used is True

        reused = await OneTimeTokenService.consume(db, raw, "reset")
        assert reused is None


@pytest.mark.asyncio
async def test_one_time_token_expiration():
    """Expired token cannot be consumed."""
    from datetime import timedelta

    from app.core.utils import utc_now

    async with AsyncSessionLocal() as db:
        from sqlalchemy import text

        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        user = User(
            email=f"tok-exp-{uuid.uuid4().hex[:6]}@example.com",
            full_name="Token Exp Test",
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(user)
        await db.flush()
        raw, token = await OneTimeTokenService.create(db, str(user.id), "reset", ttl_hours=1)
        # Force expiration
        token.expires_at = utc_now() - timedelta(minutes=1)
        await db.commit()

    async with AsyncSessionLocal() as db:
        consumed = await OneTimeTokenService.consume(db, raw, "reset")
        assert consumed is None


@pytest.mark.asyncio
async def test_one_time_token_purpose_specific():
    """Token with wrong purpose is rejected."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text

        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        user = User(
            email=f"tok-purp-{uuid.uuid4().hex[:6]}@example.com",
            full_name="Token Purpose Test",
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(user)
        await db.flush()
        raw, _ = await OneTimeTokenService.create(db, str(user.id), "activation")
        await db.commit()

    async with AsyncSessionLocal() as db:
        # Try to consume with wrong purpose
        consumed = await OneTimeTokenService.consume(db, raw, "reset")
        assert consumed is None


# ---------------------------------------------------------------------------
# DEMO SEED — password sync
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_demo_seed_password_sync():
    """Re-running demo seed with a new password syncs the hash."""
    from sqlalchemy import text

    from app.core.security import verify_password
    from app.scripts.seed_white_label_demo import _get_or_create_user

    email = f"seed-sync-{uuid.uuid4().hex[:6]}@example.com"
    password_a = "PasswordA123!"
    password_b = "PasswordB456!"

    # First seed with password A
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        user, created = await _get_or_create_user(
            db, email, WR_TENANT_ID, "Seed Sync", UserRole.ADMIN, password_a
        )
        await db.commit()
        assert created is True

    # Verify password A works
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        assert verify_password(password_a, user.password_hash)

    # Re-seed with password B
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        user, created = await _get_or_create_user(
            db, email, WR_TENANT_ID, "Seed Sync", UserRole.ADMIN, password_b
        )
        await db.commit()
        assert created is False  # user already existed

    # Verify password B works and A fails
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        assert verify_password(password_b, user.password_hash)
        assert not verify_password(password_a, user.password_hash)
