import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base
from app.core.utils import utc_now


class TenantSecret(Base):
    """Armazenamento criptografado de secrets por tenant.

    Cada par (tenant_id, key) é único. O valor é armazenado cifrado
    (Fernet) na coluna encrypted_value.
    """

    __tablename__ = "tenant_secrets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "key", name="uq_tenant_secret_key"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    key = Column(String, nullable=False, index=True)
    encrypted_value = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
