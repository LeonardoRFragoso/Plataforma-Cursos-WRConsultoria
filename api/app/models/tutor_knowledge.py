"""Modelos de base de conhecimento do Tutor NR (RAG).

Armazena documentos privados (extracted-text.md) e seus chunks de forma
tenant-aware, com rastreabilidade, versionamento por hash e isolamento
por RLS. A busca full-text usa tsvector em português.
"""

import uuid
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.utils import utc_now


class TutorKnowledgeStatus(str, PyEnum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"


class TutorKnowledgeDocument(Base):
    """Documento-fonte privado ingerido pelo Tutor NR.

    O conteúdo integral NÃO é armazenado nesta tabela — apenas metadata.
    O texto completo fica no storage privado (S3/Tebi) sob a storage_key.
    Os chunks ficam em ``TutorKnowledgeChunk``.
    """

    __tablename__ = "tutor_knowledge_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    source_slug = Column(String(100), nullable=False)
    nr_code = Column(String(20), nullable=False)
    course_variant = Column(String(100), nullable=True)
    title = Column(String(300), nullable=False)
    storage_key = Column(String(500), nullable=False)
    content_hash = Column(String(64), nullable=False)
    knowledge_version = Column(Integer, nullable=False, default=1)
    status = Column(
        Enum(TutorKnowledgeStatus),
        default=TutorKnowledgeStatus.ACTIVE,
        nullable=False,
    )
    char_count = Column(Integer, nullable=True)
    chunk_count = Column(Integer, nullable=True)
    heading_count = Column(Integer, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    chunks = relationship(
        "TutorKnowledgeChunk",
        backref="document",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "source_slug",
            "knowledge_version",
            name="uq_tutor_doc_tenant_slug_version",
        ),
        Index("ix_tutor_doc_tenant_nr", "tenant_id", "nr_code"),
        Index("ix_tutor_doc_tenant_status", "tenant_id", "status"),
    )


class TutorKnowledgeChunk(Base):
    """Fragmento de um documento-fonte, indexado para recuperação.

    O ``search_vector`` é um TSVECTOR gerado a partir do ``content`` em
    português, permitindo busca full-text lexical. O ``heading_path``
    preserva o contexto hierárquico da seção Markdown.
    """

    __tablename__ = "tutor_knowledge_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tutor_knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index = Column(Integer, nullable=False)
    heading = Column(String(500), nullable=True)
    heading_path = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    search_vector = Column(TSVECTOR, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_tutor_chunk_doc_index",
        ),
        Index("ix_tutor_chunk_tenant_doc", "tenant_id", "document_id"),
        Index("ix_tutor_chunk_tenant_active", "tenant_id", "is_active"),
    )
