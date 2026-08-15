import pytest
from sqlalchemy import select

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.models.one_time_token import OneTimeToken
from app.models.user import User, UserRole
from app.services.one_time_token_service import OneTimeTokenService


@pytest.mark.asyncio
async def test_one_time_token_lifecycle():
    """Testa criação e consumo único de token de ativação."""
    async with AsyncSessionLocal() as session:
        user = User(
            email=f"token-{id(object)}@example.com",
            full_name="Token Test",
            role=UserRole.ADMIN,
            is_active=False,
            tenant_id=WR_TENANT_ID,
        )
        session.add(user)
        await session.flush()

        raw, _ = await OneTimeTokenService.create(
            session, str(user.id), "activation"
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        consumed = await OneTimeTokenService.consume(session, raw, "activation")
        assert consumed is not None
        assert consumed.used is True

        result = await session.execute(
            select(OneTimeToken).where(OneTimeToken.id == consumed.id)
        )
        db_token = result.scalar_one()
        assert db_token.used is True

        reused = await OneTimeTokenService.consume(session, raw, "activation")
        assert reused is None

        wrong_purpose = await OneTimeTokenService.consume(session, raw, "reset")
        assert wrong_purpose is None


@pytest.mark.asyncio
async def test_password_reset_flow(client):
    """Testa forgot/reset com token one-time."""
    email = "reset-flow-test@example.com"
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            full_name="Reset Test",
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=WR_TENANT_ID,
            password_hash="$argon2id$v=19$m=65536,t=3,p=4$fake$fake",
        )
        session.add(user)
        await session.commit()

    forgot = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": email},
    )
    assert forgot.status_code == 200
    reset_token = forgot.json()["reset_token"]

    reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "newpass123"},
    )
    assert reset.status_code == 200

    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": "newpass123"},
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_reset_token_cannot_be_reused(client):
    """Um token de reset usado não pode ser reutilizado."""
    email = "reset-reuse-test@example.com"
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            full_name="Reset Reuse",
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=WR_TENANT_ID,
            password_hash="$argon2id$v=19$m=65536,t=3,p=4$fake$fake",
        )
        session.add(user)
        await session.commit()

    forgot = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": email},
    )
    reset_token = forgot.json()["reset_token"]

    first = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "newpass123"},
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "newpass123"},
    )
    assert second.status_code == 400
