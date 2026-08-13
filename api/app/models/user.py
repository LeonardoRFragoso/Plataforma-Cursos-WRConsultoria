from sqlalchemy import Column, String, DateTime, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from enum import Enum as PyEnum

from app.core.database import Base

class UserRole(str, PyEnum):
    ADMIN = "admin"
    STUDENT = "student"

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    cpf = Column(String, unique=True, index=True, nullable=True)
    full_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(
        Enum(UserRole, values_callable=lambda x: [e.value for e in x]),
        default=UserRole.STUDENT,
        nullable=False,
    )
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    student = relationship("Student", back_populates="user", uselist=False)
