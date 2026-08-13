import uuid
from enum import Enum as PyEnum

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base
from app.core.utils import utc_now


class CourseModality(str, PyEnum):
    PRESENCIAL = "PRESENCIAL"
    EAD = "EAD"
    SEMIPRESENCIAL = "SEMIPRESENCIAL"

class CourseType(str, PyEnum):
    FORMACAO = "FORMACAO"
    RECICLAGEM = "RECICLAGEM"
    INICIAL = "INICIAL"
    PERIODICO = "PERIODICO"

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
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

