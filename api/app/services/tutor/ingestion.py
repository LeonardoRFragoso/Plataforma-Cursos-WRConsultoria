"""Serviço de ingestion do Tutor NR.

Processa os 15 extracted-text.md: lê do storage privado, fragmenta em
chunks, armazena metadata no banco e garante idempotência por hash.

Fluxo:
    documento → normalização → chunks → hash → upsert no banco

Idempotência:
- Se o content_hash do documento não mudou → UNCHANGED;
- Se mudou → supersede versão antiga, cria nova versão + chunks;
- Chunks duplicados (mesmo content_hash) não são recriados.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tutor_knowledge import (
    TutorKnowledgeChunk,
    TutorKnowledgeDocument,
    TutorKnowledgeStatus,
)
from app.services.tutor.chunking import Chunk, chunk_document
from app.services.tutor.sources import KnowledgeSource, get_source

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    source_slug: str
    status: str  # CREATED | UPDATED | UNCHANGED | MISSING | ERROR
    document_id: UUID | None = None
    char_count: int = 0
    chunk_count: int = 0
    heading_count: int = 0
    content_hash: str = ""
    error: str = ""


@dataclass
class IngestionReport:
    results: list[IngestionResult] = field(default_factory=list)

    @property
    def documents_changed(self) -> int:
        return sum(1 for r in self.results if r.status in ("CREATED", "UPDATED"))

    @property
    def chunks_created(self) -> int:
        return sum(1 for r in self.results if r.status in ("CREATED", "UPDATED"))

    @property
    def unchanged(self) -> int:
        return sum(1 for r in self.results if r.status == "UNCHANGED")

    @property
    def errors(self) -> int:
        return sum(1 for r in self.results if r.status == "ERROR")

    @property
    def missing(self) -> int:
        return sum(1 for r in self.results if r.status == "MISSING")


def compute_document_hash(content: str) -> str:
    """SHA-256 do conteúdo normalizado do documento."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def count_headings(text: str) -> int:
    """Conta headings Markdown no texto."""
    import re
    return len(re.findall(r'^#{1,6}\s+', text, re.MULTILINE))


async def _find_existing_document(
    db: AsyncSession,
    tenant_id: UUID,
    source_slug: str,
) -> TutorKnowledgeDocument | None:
    result = await db.execute(
        select(TutorKnowledgeDocument)
        .where(
            TutorKnowledgeDocument.tenant_id == tenant_id,
            TutorKnowledgeDocument.source_slug == source_slug,
            TutorKnowledgeDocument.status == TutorKnowledgeStatus.ACTIVE,
        )
        .order_by(TutorKnowledgeDocument.knowledge_version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _supersede_document(
    db: AsyncSession,
    doc: TutorKnowledgeDocument,
) -> int:
    """Marca documento como SUPERSEDED e desativa seus chunks.

    Returns: número de chunks desativados.
    """
    doc.status = TutorKnowledgeStatus.SUPERSEDED
    result = await db.execute(
        text(
            "UPDATE tutor_knowledge_chunks SET is_active = false "
            "WHERE document_id = :doc_id"
        ),
        {"doc_id": str(doc.id)},
    )
    return result.rowcount or 0


async def _create_chunks(
    db: AsyncSession,
    tenant_id: UUID,
    document_id: UUID,
    chunks: list[Chunk],
) -> int:
    """Cria registros de chunk no banco. O search_vector é populado pelo trigger."""
    created = 0
    for chunk in chunks:
        db_chunk = TutorKnowledgeChunk(
            tenant_id=tenant_id,
            document_id=document_id,
            chunk_index=chunk.chunk_index,
            heading=chunk.heading,
            heading_path=chunk.heading_path,
            content=chunk.content,
            content_hash=chunk.content_hash,
            metadata=chunk.metadata,
            is_active=True,
        )
        db.add(db_chunk)
        created += 1
    await db.flush()
    return created


async def ingest_source(
    db: AsyncSession,
    tenant_id: UUID,
    source: KnowledgeSource,
    content: str,
    storage_key: str,
    *,
    dry_run: bool = False,
) -> IngestionResult:
    """Ingesta uma fonte de conhecimento no banco.

    Args:
        db: sessão async (tenant-aware)
        tenant_id: UUID do tenant
        source: KnowledgeSource do registro canônico
        content: texto Markdown do extracted-text.md
        storage_key: chave no storage privado
        dry_run: se True, apenas simula sem persistir

    Returns:
        IngestionResult com status e métricas
    """
    if not content or not content.strip():
        return IngestionResult(
            source_slug=source.slug,
            status="ERROR",
            error="Empty content",
        )

    content_hash = compute_document_hash(content)
    char_count = len(content)
    heading_count = count_headings(content)
    chunks = chunk_document(content, source.title)

    existing = await _find_existing_document(db, tenant_id, source.slug)

    if existing and existing.content_hash == content_hash:
        logger.info(
            "tutor_ingestion: source=%s UNCHANGED (hash=%s chunks=%d)",
            source.slug, content_hash[:12], existing.chunk_count,
        )
        return IngestionResult(
            source_slug=source.slug,
            status="UNCHANGED",
            document_id=existing.id,
            char_count=char_count,
            chunk_count=existing.chunk_count or len(chunks),
            heading_count=heading_count,
            content_hash=content_hash,
        )

    if dry_run:
        status = "CREATED" if not existing else "UPDATED"
        return IngestionResult(
            source_slug=source.slug,
            status=status,
            char_count=char_count,
            chunk_count=len(chunks),
            heading_count=heading_count,
            content_hash=content_hash,
        )

    # Supersede existing if present
    if existing:
        await _supersede_document(db, existing)
        new_version = existing.knowledge_version + 1
        logger.info(
            "tutor_ingestion: source=%s UPDATED (v%d→v%d)",
            source.slug, existing.knowledge_version, new_version,
        )
        status = "UPDATED"
    else:
        new_version = 1
        status = "CREATED"

    doc = TutorKnowledgeDocument(
        tenant_id=tenant_id,
        source_slug=source.slug,
        nr_code=source.nr_code,
        course_variant=source.course_variant,
        title=source.title,
        storage_key=storage_key,
        content_hash=content_hash,
        knowledge_version=new_version,
        status=TutorKnowledgeStatus.ACTIVE,
        char_count=char_count,
        chunk_count=len(chunks),
        heading_count=heading_count,
        metadata={
            "source_file": "extracted-text.md",
            "content_type": "text/markdown",
        },
    )
    db.add(doc)
    await db.flush()

    created_count = await _create_chunks(db, tenant_id, doc.id, chunks)

    logger.info(
        "tutor_ingestion: source=%s %s (v%d chunks=%d hash=%s)",
        source.slug, status, new_version, created_count, content_hash[:12],
    )

    return IngestionResult(
        source_slug=source.slug,
        status=status,
        document_id=doc.id,
        char_count=char_count,
        chunk_count=created_count,
        heading_count=heading_count,
        content_hash=content_hash,
    )


async def ingest_all(
    db: AsyncSession,
    tenant_id: UUID,
    contents: dict[str, str],
    storage_keys: dict[str, str],
    *,
    dry_run: bool = False,
    only_slugs: list[str] | None = None,
) -> IngestionReport:
    """Ingesta múltiplas fontes de conhecimento.

    Args:
        db: sessão async
        tenant_id: UUID do tenant
        contents: {slug: markdown_content}
        storage_keys: {slug: storage_key}
        dry_run: se True, simula
        only_slugs: se fornecido, processa apenas estas slugs

    Returns:
        IngestionReport consolidado
    """
    report = IngestionReport()
    from app.services.tutor.sources import SOURCES

    targets = only_slugs if only_slugs else [s.slug for s in SOURCES]

    for slug in targets:
        source = get_source(slug)
        if not source:
            report.results.append(IngestionResult(
                source_slug=slug, status="ERROR", error="Unknown source slug",
            ))
            continue

        content = contents.get(slug)
        if not content:
            report.results.append(IngestionResult(
                source_slug=slug, status="MISSING",
                error="No content provided for slug",
            ))
            continue

        storage_key = storage_keys.get(slug, "")
        result = await ingest_source(
            db, tenant_id, source, content, storage_key, dry_run=dry_run,
        )
        report.results.append(result)

    return report
