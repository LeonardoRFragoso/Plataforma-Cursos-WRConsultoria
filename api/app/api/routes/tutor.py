"""Endpoint do Tutor NR — POST /api/v1/tutor/ask.

Autenticado, rate-limited, tenant-aware. O aluno faz uma pergunta e
recebe uma resposta fundamentada na base de conhecimento privada,
com fontes, sugestões e nível de confiança.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limit import get_rate_limiter
from app.core.security import get_current_user
from app.schemas.tutor import (
    TutorAskRequest,
    TutorAskResponse,
    TutorCoverageResponse,
    TutorCoverageSource,
    TutorSource,
)
from app.services.tutor.answer import generate_answer
from app.services.tutor.retrieval import get_active_documents, get_chunk_count, retrieve
from app.services.tutor.sources import EXPECTED_SLUGS, SOURCES

logger = logging.getLogger(__name__)

router = APIRouter()

# Rate limit: 30 questions per minute per user (separate from global limit)
_TUTOR_RATE_LIMIT = 30
_TUTOR_RATE_WINDOW = 60


def _check_tutor_rate_limit(request: Request, user_id: str) -> None:
    """Rate limit específico do Tutor por usuário."""
    backend = get_rate_limiter()
    key = f"tutor:{user_id}"
    if not backend.is_allowed(key, _TUTOR_RATE_LIMIT, _TUTOR_RATE_WINDOW):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas perguntas em pouco tempo. Aguarde um momento e tente novamente.",
        )


@router.post("/ask", response_model=TutorAskResponse)
async def ask_tutor(
    request: Request,
    payload: TutorAskRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TutorAskResponse:
    """Responde uma pergunta do aluno com base na base de conhecimento.

    Requer autenticação. Rate-limited por usuário.
    """
    user_id = current_user["user_id"]
    _check_tutor_rate_limit(request, user_id)

    question = payload.question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A pergunta não pode estar vazia.",
        )

    # Convert conversation context to dicts
    context = [
        {"role": msg.role, "text": msg.text}
        for msg in payload.conversation_context
    ]

    # Retrieve relevant chunks
    retrieval_result = await retrieve(db, current_user["tenant_id"], question)

    # Generate answer
    answer = generate_answer(question, retrieval_result, context)

    logger.info(
        "tutor_ask: user=%s question=%r confidence=%s provider=%s chunks=%d",
        user_id, question[:60], answer.confidence, answer.provider,
        len(retrieval_result.chunks),
    )

    return TutorAskResponse(
        answer=answer.answer,
        sources=[TutorSource(**s) for s in answer.sources],
        suggestions=answer.suggestions,
        confidence=answer.confidence,
        scope=answer.scope,
        knowledge_level=answer.knowledge_level,
    )


@router.get("/coverage", response_model=TutorCoverageResponse)
async def get_tutor_coverage(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TutorCoverageResponse:
    """Verifica a cobertura das 15 fontes de conhecimento.

    Requer autenticação (admin ou aluno — é informação de status, não conteúdo).
    """
    tenant_id = current_user["tenant_id"]
    docs = await get_active_documents(db, tenant_id)
    total_chunks = await get_chunk_count(db, tenant_id)

    indexed_by_slug = {d.source_slug: d for d in docs}

    sources = []
    for source in SOURCES:
        doc = indexed_by_slug.get(source.slug)
        if doc:
            sources.append(TutorCoverageSource(
                slug=source.slug,
                nr_code=source.nr_code,
                course_variant=source.course_variant,
                title=source.title,
                status="indexed",
                char_count=doc.char_count or 0,
                chunk_count=doc.chunk_count or 0,
                heading_count=doc.heading_count or 0,
                content_hash=doc.content_hash,
            ))
        else:
            sources.append(TutorCoverageSource(
                slug=source.slug,
                nr_code=source.nr_code,
                course_variant=source.course_variant,
                title=source.title,
                status="missing",
            ))

    total_indexed = sum(1 for s in sources if s.status == "indexed")

    return TutorCoverageResponse(
        total_expected=len(EXPECTED_SLUGS),
        total_indexed=total_indexed,
        total_chunks=total_chunks,
        sources=sources,
        all_covered=total_indexed == len(EXPECTED_SLUGS),
    )
