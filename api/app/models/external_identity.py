import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base
from app.core.utils import utc_now


class ExternalIdentity(Base):
    """Links a local user to an external identity provider (SSO).

    The Central WR platform acts as the identity provider (IdP). When a user
    authenticates via Central WR SSO, an ``ExternalIdentity`` row records the
    mapping between the Central WR user id (``external_subject``) and the local
    LMS ``User``. This allows subsequent SSO logins to find the existing local
    user without relying on email matching alone.
    """

    __tablename__ = "external_identities"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "external_subject",
            name="uq_external_identity_provider_subject",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String(80), nullable=False, index=True)
    external_subject = Column(String(255), nullable=False, index=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime, default=utc_now, nullable=False)
    last_login_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
