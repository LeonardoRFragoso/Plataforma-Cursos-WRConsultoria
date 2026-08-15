import uuid
from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.core.constants import WR_TENANT_ID
from app.core.database import Base
from app.core.utils import utc_now


class EnrollmentStatus(str, PyEnum):
    PENDENTE = "PENDENTE"
    CONFIRMADA = "CONFIRMADA"
    CANCELADA = "CANCELADA"
    CONCLUIDA = "CONCLUIDA"

class Enrollment(Base):
    __tablename__ = "enrollments"

    __table_args__ = (
        UniqueConstraint("tenant_id", "student_id", "class_id", name="uq_enrollment_tenant_student_class"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        default=WR_TENANT_ID,
        nullable=False,
        index=True,
    )
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False)
    status = Column(Enum(EnrollmentStatus), default=EnrollmentStatus.PENDENTE, nullable=False)
    enrollment_date = Column(DateTime, default=utc_now, nullable=False)
    price = Column(Float, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
