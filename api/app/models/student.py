import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.utils import utc_now


class Student(Base):
    __tablename__ = "students"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    cpf = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True)
    company = Column(String, nullable=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    zip_code = Column(String, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User", back_populates="student")

    @property
    def email(self):
        return self.user.email if self.user else None

    @property
    def full_name(self):
        return self.user.full_name if self.user else None
