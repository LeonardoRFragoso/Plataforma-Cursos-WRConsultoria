from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Float
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid
from enum import Enum as PyEnum

from app.core.database import Base

class EnrollmentStatus(str, PyEnum):
    PENDENTE = "pendente"
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"
    CONCLUIDA = "concluida"

class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False)
    status = Column(Enum(EnrollmentStatus), default=EnrollmentStatus.PENDENTE, nullable=False)
    enrollment_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    price = Column(Float, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
