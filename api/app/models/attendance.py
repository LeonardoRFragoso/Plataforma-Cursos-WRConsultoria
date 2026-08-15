import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.core.constants import WR_TENANT_ID
from app.core.database import Base


class Attendance(Base):
    __tablename__ = "attendances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        default=WR_TENANT_ID,
        nullable=False,
        index=True,
    )
    enrollment_id = Column(UUID(as_uuid=True), ForeignKey("enrollments.id"), nullable=False)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False)
    attendance_date = Column(Date, nullable=False)
    present = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)
