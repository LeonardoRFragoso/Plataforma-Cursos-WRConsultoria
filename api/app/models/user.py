import uuid
from enum import Enum as PyEnum

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.constants import WR_TENANT_ID
from app.core.database import Base
from app.core.utils import utc_now


class UserRole(str, PyEnum):
    ADMIN = "admin"
    STUDENT = "student"
    SUPER_ADMIN = "super_admin"

class User(Base):
    __tablename__ = "users"

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),
        UniqueConstraint("tenant_id", "cpf", name="uq_user_tenant_cpf", deferrable=True, initially="DEFERRED"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        default=WR_TENANT_ID,
        nullable=False,
        index=True,
    )
    email = Column(String, index=True, nullable=False)
    cpf = Column(String, index=True, nullable=True)
    full_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(
        Enum(UserRole, values_callable=lambda x: [e.value for e in x]),
        default=UserRole.STUDENT,
        nullable=False,
    )
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    tenant = relationship("Tenant", backref="users")
    student = relationship("Student", back_populates="user", uselist=False)
