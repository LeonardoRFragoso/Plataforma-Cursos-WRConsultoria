from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid
from enum import Enum as PyEnum

from app.core.database import Base

class CourseModality(str, PyEnum):
    PRESENCIAL = "presencial"
    EAD = "ead"
    SEMIPRESENCIAL = "semipresencial"

class CourseType(str, PyEnum):
    FORMACAO = "formacao"
    RECICLAGEM = "reciclagem"
    INICIAL = "inicial"
    PERIODICO = "periodico"

class Course(Base):
    __tablename__ = "courses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    carga_horaria = Column(Integer, nullable=False)
    modality = Column(Enum(CourseModality), default=CourseModality.PRESENCIAL, nullable=False)
    tipo_curso = Column(Enum(CourseType), default=CourseType.FORMACAO, nullable=False)
    price = Column(Float, nullable=False)
    prerequisites = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

