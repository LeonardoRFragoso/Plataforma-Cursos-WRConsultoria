"""Tests for the Central WR SSO receiver (LMS side).

The Central WR backend exchange call is mocked so tests never hit the network.
Tests use the PostgreSQL test DB via the autouse ``setup_db`` fixture which
creates all tables (including ``external_identities``) via ``Base.metadata``.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.models.external_identity import ExternalIdentity
from app.models.user import User, UserRole

SSO_PROVIDER = "central-wr"


def _claims(
    sub: str = "central-user-123",
    email: str = "admin@wr.com",
    name: str = "Admin WR",
    role: str = "ADMIN",
) -> dict:
    return {
        "sub": sub,
        "email": email,
        "name": name,
        "role": role,
        "tenant_id": str(WR_TENANT_ID),
        "source": "central-wr",
    }


async def _create_user(
    email: str,
    full_name: str = "Existing Admin",
    role: UserRole = UserRole.ADMIN,
    password_hash: str | None = "hashed",
    external_subject: str | None = None,
) -> User:
    async with AsyncSessionLocal() as session:
        user = User(
            tenant_id=WR_TENANT_ID,
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            role=role,
            is_active=True,
        )
        session.add(user)
        await session.flush()
        if external_subject:
            session.add(
                ExternalIdentity(
                    provider=SSO_PROVIDER,
                    external_subject=external_subject,
                    user_id=user.id,
                    tenant_id=user.tenant_id,
                )
            )
        await session.commit()
        await session.refresh(user)
        return user


@pytest.fixture
def mock_exchange():
    """Patch the Central WR exchange call to return predetermined claims."""
    with patch(
        "app.api.routes.sso._exchange_code_with_central",
        new_callable=AsyncMock,
    ) as mocked:
        yield mocked


@pytest.fixture(autouse=True)
def _align_trusted_tenant(monkeypatch):
    """Align CENTRAL_WR_TRUSTED_TENANT_ID with test claims.

    The test claims use WR_TENANT_ID as the Central WR tenant_id. In a
    real deployment these are different UUIDs (Central WR tenant != LMS
    WR_TENANT_ID), but for testing we align them so SSO succeeds.
    Tests that specifically test cross-tenant rejection override this
    via their own monkeypatch.setattr.
    """
    monkeypatch.setattr(settings, "CENTRAL_WR_TRUSTED_TENANT_ID", str(WR_TENANT_ID))


@pytest.fixture
def mock_exchange_error():
    """Patch the Central WR exchange call to raise a CentralWrExchangeError."""
    from app.api.routes.sso import CentralWrExchangeError

    with patch(
        "app.api.routes.sso._exchange_code_with_central",
        new_callable=AsyncMock,
        side_effect=CentralWrExchangeError(400, "Código expirado"),
    ) as mocked:
        yield mocked


@pytest.mark.asyncio
async def test_sso_valid_callback_user_exists_by_external_identity(client, mock_exchange):
    """Valid callback: exchange succeeds, user exists by external identity."""
    user = await _create_user("admin@wr.com", external_subject="central-user-123")
    mock_exchange.return_value = _claims()

    response = await client.post(
        "/api/v1/sso/exchange",
        json={"code": "valid-code", "state": "state123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    # Token should contain the existing user's id.
    payload = decode_token(data["access_token"])
    assert payload["sub"] == str(user.id)
    assert payload["role"] == "admin"


@pytest.mark.asyncio
async def test_sso_account_linking_by_email_on_first_login(client, mock_exchange):
    """Account linking by email on first SSO login (no external identity yet)."""
    user = await _create_user("admin@wr.com", external_subject=None)
    mock_exchange.return_value = _claims()

    response = await client.post(
        "/api/v1/sso/exchange",
        json={"code": "valid-code", "state": "state123"},
    )

    assert response.status_code == 200
    payload = decode_token(response.json()["access_token"])
    assert payload["sub"] == str(user.id)

    # ExternalIdentity should now be linked.
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        stmt = select(ExternalIdentity).where(
            ExternalIdentity.provider == SSO_PROVIDER,
            ExternalIdentity.external_subject == "central-user-123",
        )
        result = await session.execute(stmt)
        ext = result.scalar_one_or_none()
        assert ext is not None
        assert ext.user_id == user.id


@pytest.mark.asyncio
async def test_sso_no_duplicate_when_email_matches(client, mock_exchange):
    """User is not duplicated when email matches an existing user."""
    user = await _create_user("admin@wr.com", external_subject=None)
    mock_exchange.return_value = _claims()

    await client.post(
        "/api/v1/sso/exchange",
        json={"code": "valid-code", "state": "state123"},
    )

    # Verify only one user with that email exists.
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        stmt = select(User).where(User.email == "admin@wr.com")
        result = await session.execute(stmt)
        users = result.scalars().all()
        assert len(users) == 1
        assert users[0].id == user.id


@pytest.mark.asyncio
async def test_sso_admin_role_mapped_to_lms_admin(client, mock_exchange):
    """Central ADMIN → LMS admin role."""
    await _create_user("admin@wr.com", external_subject="central-user-123")
    mock_exchange.return_value = _claims(role="ADMIN")

    response = await client.post(
        "/api/v1/sso/exchange",
        json={"code": "valid-code", "state": "state123"},
    )

    assert response.status_code == 200
    payload = decode_token(response.json()["access_token"])
    assert payload["role"] == "admin"


@pytest.mark.asyncio
async def test_sso_non_admin_role_rejected_403(client, mock_exchange):
    """Non-ADMIN role rejected with 403."""
    mock_exchange.return_value = _claims(role="STUDENT")

    response = await client.post(
        "/api/v1/sso/exchange",
        json={"code": "valid-code", "state": "state123"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_sso_session_tokens_created(client, mock_exchange):
    """Session tokens (access + refresh) are returned."""
    await _create_user("admin@wr.com", external_subject="central-user-123")
    mock_exchange.return_value = _claims()

    response = await client.post(
        "/api/v1/sso/exchange",
        json={"code": "valid-code", "state": "state123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert data["refresh_token"]
    # Both tokens should be decodable.
    decode_token(data["access_token"])
    decode_token(data["refresh_token"])


@pytest.mark.asyncio
async def test_sso_expired_code_error(client, mock_exchange_error):
    """Expired code → Central returns 400, LMS propagates as 400."""
    response = await client.post(
        "/api/v1/sso/exchange",
        json={"code": "expired-code", "state": "state123"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_sso_invalid_code_error(client, mock_exchange):
    """Invalid code → exchange returns non-200, LMS propagates error."""
    from app.api.routes.sso import CentralWrExchangeError

    mock_exchange.side_effect = CentralWrExchangeError(400, "Código inválido")

    response = await client.post(
        "/api/v1/sso/exchange",
        json={"code": "bad-code", "state": "state123"},
    )

    assert response.status_code == 400
    assert "inválido" in response.json()["detail"].lower() or "expirado" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_sso_auto_provisioning_creates_user_no_password(client, mock_exchange):
    """Auto-provisioning creates a user with no password_hash."""
    mock_exchange.return_value = _claims(
        sub="new-central-user",
        email="newadmin@wr.com",
    )

    response = await client.post(
        "/api/v1/sso/exchange",
        json={"code": "valid-code", "state": "state123"},
    )

    assert response.status_code == 200
    payload = decode_token(response.json()["access_token"])

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        stmt = select(User).where(User.id == uuid.UUID(payload["sub"]))
        result = await session.execute(stmt)
        user = result.scalar_one()
        assert user.password_hash is None
        assert user.role == UserRole.ADMIN
        assert user.is_active is True
        assert user.tenant_id == WR_TENANT_ID


@pytest.mark.asyncio
async def test_sso_external_identity_created_on_provisioning(client, mock_exchange):
    """ExternalIdentity is created on provisioning."""
    mock_exchange.return_value = _claims(
        sub="prov-user-456",
        email="provisioned@wr.com",
    )

    response = await client.post(
        "/api/v1/sso/exchange",
        json={"code": "valid-code", "state": "state123"},
    )

    assert response.status_code == 200
    payload = decode_token(response.json()["access_token"])

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        stmt = select(ExternalIdentity).where(
            ExternalIdentity.provider == SSO_PROVIDER,
            ExternalIdentity.external_subject == "prov-user-456",
        )
        result = await session.execute(stmt)
        ext = result.scalar_one_or_none()
        assert ext is not None
        assert ext.user_id == uuid.UUID(payload["sub"])


# ============================================================================
# Role reconciliation tests
# ============================================================================


@pytest.mark.asyncio
async def test_sso_existing_student_rejected_without_promotion(client, mock_exchange):
    """Central ADMIN + existing LMS student → rejected, never promoted."""
    user = await _create_user(
        "student@wr.com",
        full_name="Existing Student",
        role=UserRole.STUDENT,
        external_subject="central-student-1",
    )
    mock_exchange.return_value = _claims(
        sub="central-student-1",
        email="student@wr.com",
        role="ADMIN",
    )

    response = await client.post(
        "/api/v1/sso/exchange",
        json={"code": "valid-code", "state": "state123"},
    )

    assert response.status_code == 403

    # Verify the user's role was not changed in the database.
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        stmt = select(User).where(User.id == user.id)
        result = await session.execute(stmt)
        unchanged_user = result.scalar_one()
        assert unchanged_user.role == UserRole.STUDENT


@pytest.mark.asyncio
async def test_sso_existing_admin_stays_admin(client, mock_exchange):
    """Central ADMIN + existing LMS admin → stays admin."""
    user = await _create_user(
        "admin2@wr.com",
        full_name="Existing Admin",
        role=UserRole.ADMIN,
        external_subject="central-admin-2",
    )
    mock_exchange.return_value = _claims(
        sub="central-admin-2",
        email="admin2@wr.com",
        role="ADMIN",
    )

    response = await client.post(
        "/api/v1/sso/exchange",
        json={"code": "valid-code", "state": "state123"},
    )

    assert response.status_code == 200
    payload = decode_token(response.json()["access_token"])
    assert payload["role"] == "admin"

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        stmt = select(User).where(User.id == user.id)
        result = await session.execute(stmt)
        updated_user = result.scalar_one()
        assert updated_user.role == UserRole.ADMIN


@pytest.mark.asyncio
async def test_sso_existing_super_admin_not_downgraded(client, mock_exchange):
    """Central ADMIN + existing LMS super_admin → stays super_admin (never downgraded)."""
    user = await _create_user(
        "superadmin@wr.com",
        full_name="Super Admin",
        role=UserRole.SUPER_ADMIN,
        external_subject="central-super-1",
    )
    mock_exchange.return_value = _claims(
        sub="central-super-1",
        email="superadmin@wr.com",
        role="ADMIN",
    )

    response = await client.post(
        "/api/v1/sso/exchange",
        json={"code": "valid-code", "state": "state123"},
    )

    assert response.status_code == 200
    payload = decode_token(response.json()["access_token"])
    assert payload["role"] == "super_admin"

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        stmt = select(User).where(User.id == user.id)
        result = await session.execute(stmt)
        updated_user = result.scalar_one()
        assert updated_user.role == UserRole.SUPER_ADMIN


@pytest.mark.asyncio
async def test_sso_non_admin_no_role_change(client, mock_exchange):
    """Central non-ADMIN → 403, no role change to existing user."""
    user = await _create_user(
        "student2@wr.com",
        full_name="Student 2",
        role=UserRole.STUDENT,
        external_subject="central-student-2",
    )
    mock_exchange.return_value = _claims(
        sub="central-student-2",
        email="student2@wr.com",
        role="STUDENT",
    )

    response = await client.post(
        "/api/v1/sso/exchange",
        json={"code": "valid-code", "state": "state123"},
    )

    assert response.status_code == 403

    # Verify the user's role was NOT changed.
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        stmt = select(User).where(User.id == user.id)
        result = await session.execute(stmt)
        unchanged_user = result.scalar_one()
        assert unchanged_user.role == UserRole.STUDENT


# ============================================================================
# State parameter tests
# ============================================================================


@pytest.mark.asyncio
async def test_sso_state_passed_to_central(client, mock_exchange):
    """State parameter is forwarded to Central WR exchange call."""
    mock_exchange.return_value = _claims()

    await client.post(
        "/api/v1/sso/exchange",
        json={"code": "valid-code", "state": "my-state-value"},
    )

    # Verify _exchange_code_with_central was called with the state.
    mock_exchange.assert_called_once_with(
        "valid-code",
        "my-state-value",
        "lms-wr-cursos",
    )


@pytest.mark.asyncio
async def test_sso_empty_state_rejected_by_central(client, mock_exchange):
    """Empty state → Central rejects, LMS propagates 400."""
    from app.api.routes.sso import CentralWrExchangeError

    mock_exchange.side_effect = CentralWrExchangeError(400, "Invalid state parameter")

    response = await client.post(
        "/api/v1/sso/exchange",
        json={"code": "valid-code", "state": ""},
    )

    assert response.status_code == 400


# ============================================================================
# RLS / tenant context tests
# ============================================================================


@pytest.mark.asyncio
async def test_sso_external_identity_rls_tenant_context(client, mock_exchange):
    """ExternalIdentity operations work with the normal get_db() tenant context.

    This test proves that the SSO endpoint correctly uses the standard
    ``get_db()`` dependency which sets ``app.current_tenant`` for RLS.
    The test DB uses the WR tenant ID, matching production behavior.
    """
    mock_exchange.return_value = _claims(
        sub="rls-test-user",
        email="rls-test@wr.com",
    )

    response = await client.post(
        "/api/v1/sso/exchange",
        json={"code": "valid-code", "state": "state123"},
    )

    assert response.status_code == 200

    # Verify ExternalIdentity was created with the correct tenant_id.
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        stmt = select(ExternalIdentity).where(
            ExternalIdentity.provider == SSO_PROVIDER,
            ExternalIdentity.external_subject == "rls-test-user",
        )
        result = await session.execute(stmt)
        ext = result.scalar_one_or_none()
        assert ext is not None
        assert str(ext.tenant_id) == str(WR_TENANT_ID)


# ============================================================================
# Claim validation tests (defense in depth)
# ============================================================================


@pytest.mark.asyncio
async def test_sso_invalid_source_rejected_403(client, mock_exchange):
    """Claims with source != 'central-wr' → 403, no provisioning."""
    mock_exchange.return_value = {
        "sub": "evil-user",
        "email": "evil@wr.com",
        "name": "Evil",
        "role": "ADMIN",
        "tenant_id": str(WR_TENANT_ID),
        "source": "evil-idp",
    }

    response = await client.post(
        "/api/v1/sso/exchange",
        json={"code": "valid-code", "state": "state123"},
    )

    assert response.status_code == 403

    # No user should be provisioned.
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        stmt = select(User).where(User.email == "evil@wr.com")
        result = await session.execute(stmt)
        assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_sso_missing_tenant_id_rejected(client, mock_exchange):
    """Claims without tenant_id → 502, no provisioning."""
    mock_exchange.return_value = {
        "sub": "no-tenant-user",
        "email": "notenant@wr.com",
        "name": "No Tenant",
        "role": "ADMIN",
        "source": "central-wr",
    }

    response = await client.post(
        "/api/v1/sso/exchange",
        json={"code": "valid-code", "state": "state123"},
    )

    assert response.status_code == 502

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        stmt = select(User).where(User.email == "notenant@wr.com")
        result = await session.execute(stmt)
        assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_sso_unauthorized_central_tenant_rejected_403(client, mock_exchange, monkeypatch):
    """Claims with tenant_id != CENTRAL_WR_TRUSTED_TENANT_ID → 403."""
    # Set a trusted tenant ID that doesn't match the claims.
    monkeypatch.setattr(settings, "CENTRAL_WR_TRUSTED_TENANT_ID", str(uuid.uuid4()))

    mock_exchange.return_value = _claims()

    response = await client.post(
        "/api/v1/sso/exchange",
        json={"code": "valid-code", "state": "state123"},
    )

    assert response.status_code == 403

    # No user should be provisioned or linked.
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        stmt = select(ExternalIdentity).where(
            ExternalIdentity.provider == SSO_PROVIDER,
            ExternalIdentity.external_subject == "central-user-123",
        )
        result = await session.execute(stmt)
        assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_sso_non_admin_role_rejected_by_claims_validation(client, mock_exchange):
    """Claims with role != ADMIN → 403 via _validate_claims, no provisioning."""
    mock_exchange.return_value = _claims(role="STUDENT")

    response = await client.post(
        "/api/v1/sso/exchange",
        json={"code": "valid-code", "state": "state123"},
    )

    assert response.status_code == 403


# ============================================================================
# CRITICAL: Cross-tenant escalation test
# ============================================================================


@pytest.mark.asyncio
async def test_sso_cross_tenant_escalation_blocked(client, mock_exchange, monkeypatch):
    """CRITICAL: ADMIN from unauthorized Central WR tenant cannot escalate.

    Scenario:
    - Central WR has Tenant A (WR) and Tenant B (other company).
    - LMS has an existing super_admin: ceo@wr.com.
    - Central WR Tenant B has an ADMIN with the same email: ceo@wr.com.
    - That Tenant B ADMIN attempts SSO.

    Expected result:
    - 403 before account linking.
    - LMS super_admin remains intact.
    - No ExternalIdentity created.
    - No LMS JWT issued.
    """
    # Set the trusted Central WR tenant to the WR tenant.
    monkeypatch.setattr(settings, "CENTRAL_WR_TRUSTED_TENANT_ID", str(WR_TENANT_ID))

    # Create the existing LMS super_admin.
    super_admin = await _create_user(
        "ceo@wr.com",
        full_name="CEO WR",
        role=UserRole.SUPER_ADMIN,
        external_subject=None,
    )

    # Central WR returns claims for a DIFFERENT tenant (Tenant B).
    other_tenant_id = uuid.uuid4()
    mock_exchange.return_value = {
        "sub": "tenant-b-admin",
        "email": "ceo@wr.com",
        "name": "CEO from Tenant B",
        "role": "ADMIN",
        "tenant_id": str(other_tenant_id),
        "source": "central-wr",
    }

    response = await client.post(
        "/api/v1/sso/exchange",
        json={"code": "valid-code", "state": "state123"},
    )

    # Must be 403 — tenant not trusted.
    assert response.status_code == 403

    # Verify the super_admin's role was NOT changed.
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        stmt = select(User).where(User.id == super_admin.id)
        result = await session.execute(stmt)
        unchanged = result.scalar_one()
        assert unchanged.role == UserRole.SUPER_ADMIN

    # Verify NO ExternalIdentity was created for the Tenant B admin.
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        stmt = select(ExternalIdentity).where(
            ExternalIdentity.provider == SSO_PROVIDER,
            ExternalIdentity.external_subject == "tenant-b-admin",
        )
        result = await session.execute(stmt)
        assert result.scalar_one_or_none() is None


# ============================================================================
# Config validation tests
# ============================================================================


def test_config_default_secret_rejected_in_production(monkeypatch):
    """Default secret is rejected when ENVIRONMENT=production."""
    from app.core.config import Settings

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CENTRAL_WR_SSO_CLIENT_SECRET", "change-me-sso-secret")
    with pytest.raises(ValueError, match="change-me-sso-secret"):
        Settings()


def test_config_empty_secret_rejected_in_production(monkeypatch):
    """Empty secret is rejected in production."""
    from app.core.config import Settings

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CENTRAL_WR_SSO_CLIENT_SECRET", "")
    with pytest.raises(ValueError, match="empty"):
        Settings()


def test_config_short_secret_rejected_in_production(monkeypatch):
    """Secret shorter than 32 chars is rejected in production."""
    from app.core.config import Settings

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CENTRAL_WR_SSO_CLIENT_SECRET", "short-secret-20-chars!!")
    with pytest.raises(ValueError, match="32"):
        Settings()


def test_config_strong_secret_accepted_in_production(monkeypatch):
    """Secret >= 32 chars + valid trusted tenant + HTTPS URLs accepted."""
    from app.core.config import Settings

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CENTRAL_WR_SSO_CLIENT_SECRET", "a" * 32)
    monkeypatch.setenv("CENTRAL_WR_TRUSTED_TENANT_ID", str(uuid.uuid4()))
    monkeypatch.setenv("CENTRAL_WR_FRONTEND_URL", "https://central.example.com")
    monkeypatch.setenv("CENTRAL_WR_BACKEND_URL", "https://central-api.example.com")
    s = Settings()
    assert s.CENTRAL_WR_SSO_CLIENT_SECRET == "a" * 32


def test_config_http_url_rejected_in_production(monkeypatch):
    """HTTP URLs are rejected for SSO URLs in production."""
    from app.core.config import Settings

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CENTRAL_WR_SSO_CLIENT_SECRET", "a" * 32)
    monkeypatch.setenv("CENTRAL_WR_TRUSTED_TENANT_ID", str(uuid.uuid4()))
    monkeypatch.setenv("CENTRAL_WR_FRONTEND_URL", "http://central.example.com")
    with pytest.raises(ValueError, match="HTTPS"):
        Settings()


def test_config_trusted_tenant_empty_rejected_in_production(monkeypatch):
    """Empty CENTRAL_WR_TRUSTED_TENANT_ID is rejected in production."""
    from app.core.config import Settings

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CENTRAL_WR_SSO_CLIENT_SECRET", "a" * 32)
    monkeypatch.setenv("CENTRAL_WR_TRUSTED_TENANT_ID", "")
    monkeypatch.setenv("CENTRAL_WR_FRONTEND_URL", "https://central.example.com")
    monkeypatch.setenv("CENTRAL_WR_BACKEND_URL", "https://central-api.example.com")
    with pytest.raises(ValueError, match="CENTRAL_WR_TRUSTED_TENANT_ID"):
        Settings()


def test_config_trusted_tenant_invalid_uuid_rejected_in_production(monkeypatch):
    """Invalid UUID for CENTRAL_WR_TRUSTED_TENANT_ID is rejected in production."""
    from app.core.config import Settings

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CENTRAL_WR_SSO_CLIENT_SECRET", "a" * 32)
    monkeypatch.setenv("CENTRAL_WR_TRUSTED_TENANT_ID", "not-a-uuid")
    monkeypatch.setenv("CENTRAL_WR_FRONTEND_URL", "https://central.example.com")
    monkeypatch.setenv("CENTRAL_WR_BACKEND_URL", "https://central-api.example.com")
    with pytest.raises(ValueError, match="valid UUID"):
        Settings()


def test_config_trusted_tenant_valid_uuid_accepted_in_production(monkeypatch):
    """Valid UUID for CENTRAL_WR_TRUSTED_TENANT_ID is accepted in production."""
    from app.core.config import Settings

    valid_uuid = str(uuid.uuid4())
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CENTRAL_WR_SSO_CLIENT_SECRET", "a" * 32)
    monkeypatch.setenv("CENTRAL_WR_TRUSTED_TENANT_ID", valid_uuid)
    monkeypatch.setenv("CENTRAL_WR_FRONTEND_URL", "https://central.example.com")
    monkeypatch.setenv("CENTRAL_WR_BACKEND_URL", "https://central-api.example.com")
    s = Settings()
    assert s.CENTRAL_WR_TRUSTED_TENANT_ID == valid_uuid


def test_config_trusted_tenant_empty_allowed_in_development(monkeypatch):
    """Empty CENTRAL_WR_TRUSTED_TENANT_ID is allowed in development."""
    from app.core.config import Settings

    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("CENTRAL_WR_TRUSTED_TENANT_ID", "")
    s = Settings()
    assert s.CENTRAL_WR_TRUSTED_TENANT_ID == ""
