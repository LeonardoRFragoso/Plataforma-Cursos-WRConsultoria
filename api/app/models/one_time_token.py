import uuid
from datetime import timedelta

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base
from app.core.utils import utc_now


class OneTimeToken(Base):
    __tablename__ = "one_time_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String, nullable=False, index=True)
    purpose = Column(String, nullable=False)  # activation | reset
    used = Column(Boolean, nullable=False, default=False)
    used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=False, default=lambda: utc_now() + timedelta(hours=24))
    created_at = Column(DateTime, default=utc_now, nullable=False)
