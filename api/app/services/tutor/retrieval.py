"""Serviço de recuperação (retrieval) do Tutor NR.

Busca híbrida combinando:

1. PostgreSQL FTS em português com query OR (não AND) + prefix matching;
2. ILIKE para termos técnicos exatos (siglas, nomes de equipamentos);
3. Heading-aware boost (chunks cujo heading contém termos da pergunta);
4. Scope/variant boost (NR/variante detectada);
5. Source-aware diversity selection (garante diversidade para perguntas
   multi-source).

O retrieval é sempre broad-first: busca em todas as fontes e usa o
scope detection para boost, não para filtragem restritiva.
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
from app.services.tutor.aliases import expand_query
from app.services.tutor.scope import ScopeDetection, detect_scope

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 6
MAX_TOP_K = 12
# Over-fetch factor: retrieve more candidates than needed for diversity selection
CANDIDATE_MULTIPLIER = 3

# Score weights for hybrid ranking
W_FTS = 1.0          # FTS rank (ts_rank_cd, typically 0.01-0.5)
W_EXACT_TERM = 0.15  # Per exact term match in content (ILIKE)
W_HEADING = 0.25     # Per exact term match in heading
W_SCOPE = 1.0        # Scope boost (applied as-is from detection)
W_VARIANT_DISC = 0.5 # Variant discriminator boost


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
    exact_term_score: float
    heading_boost: float
    final_score: float


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk] = field(default_factory=list)
    scope: ScopeDetection | None = None
    total_found: int = 0
    # Debug info (sem conteúdo privado)
    debug: dict = field(default_factory=dict)


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
    """Constrói uma query tsquery com operador OR e prefix matching.

    Usa OR (|) para que chunks que contenham QUALQUER termo sejam
    recuperados, e prefix matching (:*) para flexibilidade lexical.

    Isso é fundamental para perguntas em linguagem natural onde
    nem todos os termos aparecem no mesmo chunk.
    """
    terms = [t for t in normalized.split() if len(t) > 1]
    if not terms:
        return ''
    # Join with OR and add prefix matching
    return ' | '.join(f'{t}:*' for t in terms[:20])  # Cap at 20 terms


def _extract_exact_terms(question: str, scope: ScopeDetection) -> list[str]:
    """Extrai termos técnicos exatos para matching ILIKE.

    Inclui:
    - Siglas/tokens curtos discriminativos (SEP, CA, EPI, etc.)
    - Termos de scope detection
    - Nomes de equipamentos
    """
    normalized = _normalize_for_fts(question)
    tokens = re.findall(r'\b\w+\b', normalized)

    # Termos discriminativos de todas as fontes (para matching exato)
    from app.services.tutor.sources import SOURCES
    all_disc_terms: set[str] = set()
    for source in SOURCES:
        for term in source.discriminator_terms:
            all_disc_terms.add(_normalize_for_fts(term))

    # Termos de scope detectados
    scope_terms: set[str] = set()
    for slug in scope.source_slugs:
        from app.services.tutor.sources import get_source
        src = get_source(slug)
        if src:
            for term in src.scope_terms:
                scope_terms.add(_normalize_for_fts(term))

    exact_terms: list[str] = []

    # 1. Tokens que são termos discriminativos conhecidos
    for token in tokens:
        if token in all_disc_terms and len(token) >= 2:
            exact_terms.append(token)

    # 2. Siglas (2-5 chars, todas maiúsculas no original)
    upper_tokens = re.findall(r'\b[A-Z]{2,5}\b', question)
    for ut in upper_tokens:
        norm = _normalize_for_fts(ut)
        if norm not in exact_terms and len(norm) >= 2:
            exact_terms.append(norm)

    # 3. Termos de scope multi-palavra que aparecem na pergunta
    for st in scope_terms:
        if ' ' in st and st in normalized:
            if st not in exact_terms:
                exact_terms.append(st)

    # 4. Nomes de equipamentos específicos
    equipment_terms = [
        "empilhadeira", "guindauto", "munck", "minicarregadeira",
        "ponte rolante", "retroescavadeira", "plataforma elevatoria",
        "plataforma elevatória", "cesta elevatoria", "cesta elevatória",
        "talha", "guincho", "portico", "pórtico", "bobcat",
    ]
    for et in equipment_terms:
        norm_et = _normalize_for_fts(et)
        if norm_et in normalized and norm_et not in exact_terms:
            exact_terms.append(norm_et)

    return exact_terms


def _build_exact_term_conditions(
    exact_terms: list[str],
) -> tuple[str, dict]:
    """Constrói condições SQL ILIKE para termos exatos.

    Retorna (sql_fragment, params) que pode ser usado no SELECT
    para computar um score de matching exato.
    """
    if not exact_terms:
        return "0.0", {}

    parts: list[str] = []
    params: dict = {}
    for i, term in enumerate(exact_terms):
        param_name = f"et_{i}"
        # ILIKE é case-insensitive e accent-insensitive não é garantido,
        # mas o content já está normalizado no chunking? Não — o content
        # preserva acentos. Usamos ILIKE que é case-insensitive.
        # Para matching accent-insensitive, usamos unaccent se disponível,
        # mas para simplicidade, fazemos ILIKE no content/heading.
        parts.append(
            f"(CASE WHEN c.content ILIKE :{param_name} THEN 1 ELSE 0 END)"
        )
        params[param_name] = f"%{term}%"

    score_expr = " + ".join(parts)
    return score_expr, params


def _build_heading_conditions(
    exact_terms: list[str],
) -> tuple[str, dict]:
    """Constrói condições SQL para boost de heading."""
    if not exact_terms:
        return "0.0", {}

    parts: list[str] = []
    params: dict = {}
    for i, term in enumerate(exact_terms):
        param_name = f"ht_{i}"
        parts.append(
            f"(CASE WHEN COALESCE(c.heading, '') ILIKE :{param_name} THEN 1 ELSE 0 END)"
        )
        params[param_name] = f"%{term}%"

    score_expr = " + ".join(parts)
    return score_expr, params


def _diversity_aware_select(
    chunks: list[RetrievedChunk],
    top_k: int,
    scope: ScopeDetection,
) -> list[RetrievedChunk]:
    """Seleção com diversidade de fontes (source-aware MMR simplificado).

    Garante que perguntas multi-source (ex: "diferença entre NR-10 Básico e SEP")
    tenham chunks de ambas as fontes, não apenas da de maior score.

    Estratégia:
    1. Se scope detectou múltiplas fontes, aloca slots por fonte proporcionalmente;
    2. Para cada fonte, pega os melhores chunks por score;
    3. Se sobram slots, preenche com os melhores restantes globais.
    """
    if len(chunks) <= top_k:
        return sorted(chunks, key=lambda c: c.final_score, reverse=True)

    # Se não há múltiplas fontes detectadas, usa ranking puro
    if len(scope.source_slugs) <= 1:
        return sorted(chunks, key=lambda c: c.final_score, reverse=True)[:top_k]

    # Agrupa por source_slug
    by_source: dict[str, list[RetrievedChunk]] = {}
    for chunk in chunks:
        by_source.setdefault(chunk.source_slug, []).append(chunk)

    # Ordena cada grupo por score
    for slug in by_source:
        by_source[slug].sort(key=lambda c: c.final_score, reverse=True)

    # Alocação: pelo menos 1 slot por fonte detectada, restante distribuído
    detected_slugs = [s for s in scope.source_slugs if s in by_source]
    if not detected_slugs:
        return sorted(chunks, key=lambda c: c.final_score, reverse=True)[:top_k]

    # Slots mínimos por fonte detectada
    min_per_source = max(1, top_k // len(detected_slugs))
    selected: list[RetrievedChunk] = []
    used_ids: set[UUID] = set()

    # Primeira passada: min_per_source chunks de cada fonte detectada
    for slug in detected_slugs:
        for chunk in by_source[slug][:min_per_source]:
            if chunk.chunk_id not in used_ids:
                selected.append(chunk)
                used_ids.add(chunk.chunk_id)

    # Segunda passada: preenche slots restantes com melhores globais
    remaining = [c for c in sorted(chunks, key=lambda c: c.final_score, reverse=True)
                 if c.chunk_id not in used_ids]
    for chunk in remaining:
        if len(selected) >= top_k:
            break
        selected.append(chunk)
        used_ids.add(chunk.chunk_id)

    # Re-ordena por score final
    selected.sort(key=lambda c: c.final_score, reverse=True)
    return selected[:top_k]


async def retrieve(
    db: AsyncSession,
    tenant_id: UUID,
    question: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    scope: ScopeDetection | None = None,
    conversation_context: list[dict] | None = None,
) -> RetrievalResult:
    """Recupera chunks relevantes para uma pergunta usando busca híbrida.

    Args:
        db: sessão async (tenant-aware, RLS ativo)
        tenant_id: UUID do tenant
        question: pergunta do aluno
        top_k: número máximo de chunks a retornar
        scope: detecção de escopo pré-computada (opcional)
        conversation_context: histórico recente para expansão de follow-ups

    Returns:
        RetrievalResult com chunks ranqueados por final_score
    """
    # Query expansion: usa contexto de conversa para expandir follow-ups
    expanded_question = _expand_with_context(question, conversation_context)

    # Alias expansion: adiciona sinônimos semânticos
    expanded_question = expand_query(expanded_question)

    if scope is None:
        scope = detect_scope(expanded_question)

    top_k = min(max(top_k, 1), MAX_TOP_K)
    normalized = _normalize_for_fts(expanded_question)
    fts_query_str = _build_fts_query(normalized)

    if not fts_query_str:
        return RetrievalResult(scope=scope, total_found=0)

    # Extrai termos exatos para ILIKE boost
    exact_terms = _extract_exact_terms(expanded_question, scope)

    # Build scope boost expression
    scope_boost_expr = "0.0"
    if scope.slug_scores:
        case_parts = []
        for slug, score in scope.slug_scores.items():
            case_parts.append(f"WHEN d.source_slug = '{slug}' THEN {score}")
        if case_parts:
            scope_boost_expr = f"CASE {' '.join(case_parts)} ELSE 0.0 END"

    # Build exact term score expression
    exact_score_expr, exact_params = _build_exact_term_conditions(exact_terms)
    heading_score_expr, heading_params = _build_heading_conditions(exact_terms)

    # Variant discriminator boost: se scope detectou variantes específicas,
    # boosta chunks dessas variantes adicionalmente
    variant_boost_expr = "0.0"
    if scope.slug_scores:
        # Variantes com score alto (> 5.0 indicam discriminação forte)
        variant_slugs = [s for s, sc in scope.slug_scores.items() if sc > 5.0]
        if variant_slugs:
            case_parts = []
            for slug in variant_slugs:
                case_parts.append(f"WHEN d.source_slug = '{slug}' THEN {W_VARIANT_DISC}")
            variant_boost_expr = f"CASE {' '.join(case_parts)} ELSE 0.0 END"

    # Hybrid SQL: FTS (OR semantics) + exact term ILIKE + heading boost + scope boost
    # Usa to_tsquery com OR (|) em vez de plainto_tsquery (AND)
    # FTS rank é normalizado com LEAST(..., 1.0) para evitar que matches
    # de termos comuns (quem, pode, trabalhar) dominem o ranking.
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
            LEAST(ts_rank_cd(c.search_vector, to_tsquery('portuguese', :fts_q)), 1.0) AS fts_rank,
            ({scope_boost_expr}) AS scope_boost,
            ({exact_score_expr}) AS exact_term_score,
            ({heading_score_expr}) AS heading_boost,
            ({variant_boost_expr}) AS variant_boost
        FROM tutor_knowledge_chunks c
        JOIN tutor_knowledge_documents d ON c.document_id = d.id
        WHERE c.tenant_id = :tenant_id
          AND d.tenant_id = :tenant_id
          AND c.is_active = true
          AND d.status = 'ACTIVE'
          AND (
              c.search_vector @@ to_tsquery('portuguese', :fts_q)
              OR ({exact_score_expr}) > 0
          )
        ORDER BY (
            LEAST(ts_rank_cd(c.search_vector, to_tsquery('portuguese', :fts_q)), 1.0) * {W_FTS}
            + ({scope_boost_expr}) * {W_SCOPE}
            + ({exact_score_expr}) * {W_EXACT_TERM}
            + ({heading_score_expr}) * {W_HEADING}
            + ({variant_boost_expr})
        ) DESC
        LIMIT :limit
    """)

    params = {
        "fts_q": fts_query_str,
        "tenant_id": tenant_id,
        "limit": top_k * CANDIDATE_MULTIPLIER,
    }
    params.update(exact_params)
    params.update(heading_params)

    try:
        result = await db.execute(sql, params)
        rows = result.fetchall()
    except Exception as exc:
        logger.warning("tutor_retrieval: SQL failed, falling back to FTS-only: %s", exc)
        # Fallback: FTS-only com OR semantics
        rows = await _fts_only_fallback(
            db, tenant_id, fts_query_str, scope_boost_expr, top_k * CANDIDATE_MULTIPLIER
        )

    chunks: list[RetrievedChunk] = []
    for row in rows:
        fts_rank = float(row.fts_rank or 0)
        scope_boost = float(row.scope_boost or 0)
        exact_term_score = float(row.exact_term_score or 0)
        heading_boost_val = float(row.heading_boost or 0)
        variant_boost = float(row.variant_boost or 0)

        final_score = (
            fts_rank * W_FTS
            + scope_boost * W_SCOPE
            + exact_term_score * W_EXACT_TERM
            + heading_boost_val * W_HEADING
            + variant_boost
        )

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
            exact_term_score=exact_term_score,
            heading_boost=heading_boost_val,
            final_score=final_score,
        ))

    # Scope-only fallback: se scope detectou uma fonte mas ela não aparece
    # nos resultados (termo não está no material), busca chunks dessa fonte
    # diretamente com score baseado no scope_boost.
    if scope.slug_scores:
        # Threshold: 4.0 = pelo menos um scope_term match
        strong_slugs = [s for s, sc in scope.slug_scores.items() if sc >= 4.0]
        missing_strong = [s for s in strong_slugs
                          if s not in {c.source_slug for c in chunks}]
        if missing_strong:
            # Add up to 2 chunks per missing source
            fallback_limit = min(len(missing_strong) * 2, top_k)
            fallback_chunks = await _scope_only_fallback(
                db, tenant_id, missing_strong, fallback_limit
            )
            chunks.extend(fallback_chunks)

    # Diversity-aware selection
    chunks = _diversity_aware_select(chunks, top_k, scope)

    # Debug info (sem conteúdo privado)
    selected_sources = list({c.source_slug for c in chunks})
    debug = {
        "detected_scope": scope.source_slugs,
        "scope_scores": scope.slug_scores,
        "exact_terms": exact_terms,
        "fts_query": fts_query_str,
        "expanded_question": expanded_question != question,
        "candidates_found": len(rows),
        "selected_sources": selected_sources,
        "top_score": chunks[0].final_score if chunks else 0.0,
        "top_fts_rank": chunks[0].fts_rank if chunks else 0.0,
        "top_scope_boost": chunks[0].scope_boost if chunks else 0.0,
        "top_exact_term_score": chunks[0].exact_term_score if chunks else 0.0,
        "top_heading_boost": chunks[0].heading_boost if chunks else 0.0,
    }

    logger.info(
        "tutor_retrieval: question=%r scope_slugs=%s exact_terms=%s chunks_found=%d "
        "top_score=%.3f sources=%s",
        question[:60], scope.source_slugs, exact_terms[:5], len(chunks),
        chunks[0].final_score if chunks else 0.0, selected_sources,
    )

    return RetrievalResult(chunks=chunks, scope=scope, total_found=len(chunks), debug=debug)


async def _scope_only_fallback(
    db: AsyncSession,
    tenant_id: UUID,
    source_slugs: list[str],
    limit: int,
) -> list[RetrievedChunk]:
    """Fallback: busca chunks de fontes detectadas via scope,
    mesmo sem match FTS/exato. Usa score baseado no scope_boost para
    competir com matches FTS fracos de fontes erradas.
    """
    if not source_slugs or limit <= 0:
        return []
    slugs_list = ",".join(f"'{s}'" for s in source_slugs)
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
            d.title
        FROM tutor_knowledge_chunks c
        JOIN tutor_knowledge_documents d ON c.document_id = d.id
        WHERE c.tenant_id = :tenant_id
          AND d.tenant_id = :tenant_id
          AND c.is_active = true
          AND d.status = 'ACTIVE'
          AND d.source_slug IN ({slugs_list})
        ORDER BY c.chunk_index
        LIMIT :limit
    """)
    result = await db.execute(sql, {"tenant_id": tenant_id, "limit": limit})
    rows = result.fetchall()

    chunks: list[RetrievedChunk] = []
    for row in rows:
        # Score: scope_boost * W_SCOPE — alto o suficiente para superar
        # FTS matches fracos de fontes erradas, mas não para dominar
        # matches fortes da fonte certa.
        scope_score = 4.0
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
            fts_rank=0.0,
            scope_boost=scope_score,
            exact_term_score=0.0,
            heading_boost=0.0,
            final_score=scope_score * W_SCOPE,
        ))
    return chunks


async def _fts_only_fallback(
    db: AsyncSession,
    tenant_id: UUID,
    fts_query_str: str,
    scope_boost_expr: str,
    limit: int,
) -> list:
    """Fallback: FTS-only com OR semantics se a query híbrida falhar."""
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
            LEAST(ts_rank_cd(c.search_vector, to_tsquery('portuguese', :fts_q)), 1.0) AS fts_rank,
            ({scope_boost_expr}) AS scope_boost,
            0.0 AS exact_term_score,
            0.0 AS heading_boost,
            0.0 AS variant_boost
        FROM tutor_knowledge_chunks c
        JOIN tutor_knowledge_documents d ON c.document_id = d.id
        WHERE c.tenant_id = :tenant_id
          AND d.tenant_id = :tenant_id
          AND c.is_active = true
          AND d.status = 'ACTIVE'
          AND c.search_vector @@ to_tsquery('portuguese', :fts_q)
        ORDER BY (
            LEAST(ts_rank_cd(c.search_vector, to_tsquery('portuguese', :fts_q)), 1.0)
            + ({scope_boost_expr})
        ) DESC
        LIMIT :limit
    """)
    result = await db.execute(sql, {"fts_q": fts_query_str, "tenant_id": tenant_id, "limit": limit})
    return result.fetchall()


def _expand_with_context(
    question: str,
    conversation_context: list[dict] | None,
) -> str:
    """Expande follow-ups usando o contexto da conversa.

    Se a pergunta atual contém pronomes ou referências ambíguas
    ("ele", "nele", "isso", "esse"), e há contexto anterior, tenta
    identificar o tema da pergunta anterior e expandir.

    Exemplo:
        Contexto: "O que significa SEP?"
        Pergunta: "E quem pode trabalhar nele?"
        → "E quem pode trabalhar nele? SEP sistema elétrico de potência"
    """
    if not conversation_context:
        return question

    # Pronomes indicativos de follow-up
    followup_pronouns = ['nele', 'nela', 'neles', 'nelas', 'isso', 'esse', 'essa',
                         'ele', 'ela', 'eles', 'elas', 'nisto', 'nisso']
    normalized_q = _normalize_for_fts(question)

    has_pronoun = any(p in normalized_q.split() for p in followup_pronouns)
    if not has_pronoun:
        return question

    # Pega a última pergunta do usuário no contexto
    last_user_question = None
    for msg in reversed(conversation_context):
        if msg.get("role") == "user":
            last_user_question = msg.get("text", "")
            break

    if not last_user_question:
        return question

    # Detecta scope da pergunta anterior
    prev_scope = detect_scope(last_user_question)
    if not prev_scope.source_slugs:
        return question

    # Extrai termos-chave da pergunta anterior para expandir
    # Usa apenas discriminator_terms (mais específicos) para evitar
    # que termos genéricos de scope_terms causem matches em fontes erradas
    from app.services.tutor.sources import get_source
    expansion_terms: list[str] = []
    for slug in prev_scope.source_slugs[:2]:  # Top 2 fontes
        src = get_source(slug)
        if src:
            # Usa apenas o primeiro discriminator term (mais específico)
            if src.discriminator_terms:
                expansion_terms.append(src.discriminator_terms[0])

    if expansion_terms:
        return question + ' ' + ' '.join(expansion_terms[:2])

    return question


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
