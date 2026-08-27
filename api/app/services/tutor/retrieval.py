"""Serviço de recuperação (retrieval) do Tutor NR.

Busca chunks relevantes usando PostgreSQL full-text search em português,
com boosting por escopo (NR/variante) e ranking por relevância lexical.

O retrieval é sempre broad-first: busca em todas as fontes e usa o
scope detection para boost, não para filtragem restritiva. Isso permite
perguntas multi-NR sem perder fontes relevantes.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tutor_knowledge import (
    TutorKnowledgeChunk,
    TutorKnowledgeDocument,
    TutorKnowledgeStatus,
)
from app.services.tutor.scope import ScopeDetection, detect_scope

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 6
MAX_TOP_K = 12


@dataclass
class RetrievedChunk:
    chunk_id: UUID
    document_id: UUID
    source_slug: str
    nr_code: str
    course_variant: str
    title: str
    heading: str | None
    heading_path: str | None
    content: str
    content_hash: str
    fts_rank: float
    scope_boost: float
    final_score: float


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk] = field(default_factory=list)
    scope: ScopeDetection | None = None
    total_found: int = 0


def _normalize_for_fts(query: str) -> str:
    """Normaliza a query para busca full-text em português.

    Remove acentos e caracteres especiais, mantendo termos técnicos.
    """
    nfkd = unicodedata.normalize('NFD', query)
    no_accents = ''.join(c for c in nfkd if not unicodedata.combining(c))
    # Remove punctuation but keep alphanumerics and spaces
    cleaned = re.sub(r'[^\w\s]', ' ', no_accents.lower())
    # Collapse whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def _build_fts_query(normalized: str) -> str:
    """Constrói uma query tsquery com operador OR (:flexível).

    Usa prefix matching (:*) para termos parciais.
    """
    terms = [t for t in normalized.split() if len(t) > 1]
    if not terms:
        return ''
    # Join with OR and add prefix matching
    return ' | '.join(f'{t}:*' for t in terms[:20])  # Cap at 20 terms


async def retrieve(
    db: AsyncSession,
    tenant_id: UUID,
    question: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    scope: ScopeDetection | None = None,
) -> RetrievalResult:
    """Recupera chunks relevantes para uma pergunta.

    Args:
        db: sessão async (tenant-aware, RLS ativo)
        tenant_id: UUID do tenant
        question: pergunta do aluno
        top_k: número máximo de chunks a retornar
        scope: detecção de escopo pré-computada (opcional)

    Returns:
        RetrievalResult com chunks ranqueados por final_score
    """
    if scope is None:
        scope = detect_scope(question)

    top_k = min(max(top_k, 1), MAX_TOP_K)
    normalized = _normalize_for_fts(question)
    fts_query = _build_fts_query(normalized)

    if not fts_query:
        return RetrievalResult(scope=scope, total_found=0)

    # Build the search query with FTS ranking + scope boost
    # We join chunks with documents to get source metadata
    # The ts_rank_cd weighs heading (A) > heading_path (B) > content (C)
    scope_boost_expr = "0.0"
    if scope.slug_scores:
        # Build CASE expression for scope boosting
        case_parts = []
        for slug, score in scope.slug_scores.items():
            case_parts.append(f"WHEN d.source_slug = '{slug}' THEN {score}")
        if case_parts:
            scope_boost_expr = f"CASE {' '.join(case_parts)} ELSE 0.0 END"

    sql = text(f"""
        SELECT
            c.id AS chunk_id,
            c.document_id,
            c.heading,
            c.heading_path,
            c.content,
            c.content_hash,
            d.source_slug,
            d.nr_code,
            d.course_variant,
            d.title,
            ts_rank_cd(c.search_vector, plainto_tsquery('portuguese', :q)) AS fts_rank,
            ({scope_boost_expr}) AS scope_boost
        FROM tutor_knowledge_chunks c
        JOIN tutor_knowledge_documents d ON c.document_id = d.id
        WHERE c.tenant_id = :tenant_id
          AND d.tenant_id = :tenant_id
          AND c.is_active = true
          AND d.status = 'ACTIVE'
          AND c.search_vector @@ plainto_tsquery('portuguese', :q)
        ORDER BY (ts_rank_cd(c.search_vector, plainto_tsquery('portuguese', :q))
                  + ({scope_boost_expr})) DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, {"q": normalized, "tenant_id": tenant_id, "limit": top_k * 2})
    rows = result.fetchall()

    chunks: list[RetrievedChunk] = []
    for row in rows:
        fts_rank = float(row.fts_rank or 0)
        scope_boost = float(row.scope_boost or 0)
        final_score = fts_rank + scope_boost
        chunks.append(RetrievedChunk(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            source_slug=row.source_slug,
            nr_code=row.nr_code,
            course_variant=row.course_variant or "",
            title=row.title,
            heading=row.heading,
            heading_path=row.heading_path,
            content=row.content,
            content_hash=row.content_hash,
            fts_rank=fts_rank,
            scope_boost=scope_boost,
            final_score=final_score,
        ))

    # Sort by final score and take top_k
    chunks.sort(key=lambda c: c.final_score, reverse=True)
    chunks = chunks[:top_k]

    logger.info(
        "tutor_retrieval: question=%r scope_slugs=%s chunks_found=%d top_score=%.3f",
        question[:60], scope.source_slugs, len(chunks),
        chunks[0].final_score if chunks else 0.0,
    )

    return RetrievalResult(chunks=chunks, scope=scope, total_found=len(chunks))


async def get_active_documents(
    db: AsyncSession,
    tenant_id: UUID,
) -> list[TutorKnowledgeDocument]:
    """Retorna todos os documentos ativos do tenant (para coverage check)."""
    result = await db.execute(
        select(TutorKnowledgeDocument)
        .where(
            TutorKnowledgeDocument.tenant_id == tenant_id,
            TutorKnowledgeDocument.status == TutorKnowledgeStatus.ACTIVE,
        )
        .order_by(TutorKnowledgeDocument.nr_code, TutorKnowledgeDocument.source_slug)
    )
    return list(result.scalars().all())


async def get_chunk_count(
    db: AsyncSession,
    tenant_id: UUID,
) -> int:
    """Retorna o número total de chunks ativos do tenant."""
    result = await db.execute(
        select(func.count())
        .select_from(TutorKnowledgeChunk)
        .where(
            TutorKnowledgeChunk.tenant_id == tenant_id,
            TutorKnowledgeChunk.is_active == True,
        )
    )
    return result.scalar() or 0
