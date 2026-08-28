"""B2B API client model for service-to-service authentication.

Central WR uses B2B clients to query academic data from the LMS in
read-only mode. Each client is tenant-scoped and has a set of allowed
scopes. The secret is stored as a hash (never plaintext).
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.utils import utc_now


class B2BClient(Base):
    """A registered B2B API client (e.g. Central WR backend).

    B2B clients authenticate via ``client_id`` + ``client_secret`` and
    are restricted to the scopes listed in ``allowed_scopes`` (comma-
    separated). All data access is tenant-scoped to ``tenant_id``.
    """

    __tablename__ = "b2b_clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    client_id = Column(String, unique=True, index=True, nullable=False)
    client_secret_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)
    allowed_scopes = Column(Text, nullable=False, default="academic:read")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    tenant = relationship("Tenant")
