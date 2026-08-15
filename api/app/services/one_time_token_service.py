import hashlib
import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import utc_now
from app.models.one_time_token import OneTimeToken


class OneTimeTokenService:
    @staticmethod
    def _hash(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()

    @staticmethod
    def _generate() -> str:
        return secrets.token_urlsafe(32)

    @classmethod
    async def create(
        cls,
        db: AsyncSession,
        user_id: str,
        purpose: str,
        ttl_hours: int = 24,
    ) -> tuple[str, OneTimeToken]:
        raw = cls._generate()
        token = OneTimeToken(
            user_id=user_id,
            token_hash=cls._hash(raw),
            purpose=purpose,
            expires_at=utc_now() + timedelta(hours=ttl_hours),
        )
        db.add(token)
        await db.flush()
        return raw, token

    @classmethod
    async def consume(
        cls,
        db: AsyncSession,
        raw_token: str,
        purpose: str,
    ) -> OneTimeToken | None:
        token_hash = cls._hash(raw_token)
        stmt = (
            select(OneTimeToken)
            .where(
                OneTimeToken.token_hash == token_hash,
                OneTimeToken.purpose == purpose,
                OneTimeToken.used == False,
                OneTimeToken.expires_at > utc_now(),
            )
        )
        result = await db.execute(stmt)
        token = result.scalar_one_or_none()
        if not token:
            return None

        token.used = True
        token.used_at = utc_now()
        await db.flush()
        return token
