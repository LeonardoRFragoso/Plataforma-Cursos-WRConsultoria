"""Detecção de escopo para o Tutor NR.

Identifica quais NRs/variantes são relevantes para uma pergunta do
aluno, melhorando o ranking sem limitar a busca quando uma pergunta
envolve mais de um treinamento.

Melhorias nesta versão:
- Detecção de variante mais precisa (NR-10 Básico vs SEP, NR-11 por
  equipamento, NR-33 Autorizado vs Supervisor);
- Discriminadores mais fortes para evitar wrong-variant;
- Detecção de perguntas comparativas (multi-variante intencional).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.services.tutor.sources import SOURCES, get_sources_by_nr


def _normalize(text: str) -> str:
    """Normaliza texto: remove acentos, lowercase, mantém alfanuméricos."""
    nfkd = unicodedata.normalize('NFD', text)
    no_accents = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return no_accents.lower().strip()


def _term_matches(term: str, text: str) -> bool:
    """Verifica se um termo aparece no texto com boundary matching.

    Para termos de palavra única, usa word-boundary para evitar matches
    parciais (ex: "ca" em "seguranca"). Para termos multi-palavra,
    usa substring matching (já que as palavras individuais delimitam).
    """
    if not term:
        return False
    if ' ' in term:
        return term in text
    # Single-word term: use word boundary
    pattern = r'\b' + re.escape(term) + r'\b'
    return bool(re.search(pattern, text))


@dataclass
class ScopeDetection:
    """Resultado da detecção de escopo."""
    # Slugs das fontes detectadas como relevantes
    source_slugs: list[str] = field(default_factory=list)
    # NRs detectadas (ex: NR-10, NR-35)
    nr_codes: list[str] = field(default_factory=list)
    # Score por slug (para boosting no ranking)
    slug_scores: dict[str, float] = field(default_factory=dict)
    # Se a pergunta menciona explicitamente uma NR
    has_explicit_nr: bool = False
    # Se a pergunta é comparativa entre variantes
    is_comparative: bool = False


# Padrões que indicam pergunta comparativa entre variantes
_COMPARATIVE_PATTERNS = re.compile(
    r'\b(diferen[çc]a|diferen[çc]as|comparar|comparacao|comparação|'
    r'versus|vs\b|entre)\b',
    re.IGNORECASE,
)


def detect_scope(question: str) -> ScopeDetection:
    """Detecta o escopo de uma pergunta.

    Retorna os slugs relevantes e seus scores. Não limita a busca —
    apenas fornece boosting para o ranking.

    Exemplos:
        "qual EPI devo utilizar?" → nr06
        "o que é SEP?" → nr10-sep
        "como funciona trabalho em altura?" → nr35
        "empilhadeira" → nr11-empilhadeira
        "qual diferença entre NR-10 Básico e SEP?" → nr10-basico + nr10-sep
    """
    normalized = _normalize(question)
    detection = ScopeDetection()

    # Detect comparative questions
    if _COMPARATIVE_PATTERNS.search(normalized):
        detection.is_comparative = True

    # Detect explicit NR mentions (NR-10, NR10, nr 10)
    nr_pattern = re.compile(r'\bnr\s*-?\s*(\d{1,2})\b')
    for match in nr_pattern.finditer(normalized):
        nr_num = match.group(1)
        nr_code = f"NR-{nr_num}"
        if nr_code not in detection.nr_codes:
            detection.nr_codes.append(nr_code)
            detection.has_explicit_nr = True
            # Add all variants of this NR with moderate score
            for src in get_sources_by_nr(nr_code):
                if src.slug not in detection.source_slugs:
                    detection.source_slugs.append(src.slug)
                    detection.slug_scores[src.slug] = 3.0  # Base score for NR mention

    # Check scope terms for each source
    for source in SOURCES:
        for term in source.scope_terms:
            norm_term = _normalize(term)
            if _term_matches(norm_term, normalized):
                if source.slug not in detection.source_slugs:
                    detection.source_slugs.append(source.slug)
                    detection.slug_scores[source.slug] = detection.slug_scores.get(source.slug, 0) + 4.0
                else:
                    detection.slug_scores[source.slug] = detection.slug_scores.get(source.slug, 0) + 1.0

    # Apply discriminator terms for variant disambiguation
    # Group detected sources by NR
    nr_groups: dict[str, list[str]] = {}
    for slug in detection.source_slugs:
        source = next((s for s in SOURCES if s.slug == slug), None)
        if source:
            nr_groups.setdefault(source.nr_code, []).append(slug)

    for nr_code, slugs in nr_groups.items():
        if len(slugs) <= 1:
            continue

        # Multiple variants of same NR detected — use discriminators
        # In comparative questions, we WANT to keep all variants
        if detection.is_comparative:
            # Boost all variants equally — comparative question
            for slug in slugs:
                detection.slug_scores[slug] += 3.0
            continue

        # Non-comparative: use discriminators to pick the best variant
        disc_scores: dict[str, float] = {}
        for slug in slugs:
            source = next((s for s in SOURCES if s.slug == slug), None)
            if not source:
                continue
            disc_score = 0.0
            for disc_term in source.discriminator_terms:
                norm_disc = _normalize(disc_term)
                if _term_matches(norm_disc, normalized):
                    disc_score += 6.0
            disc_scores[slug] = disc_score

        # Find best variant
        best_slug = max(disc_scores, key=disc_scores.get) if disc_scores else None
        best_disc_score = disc_scores.get(best_slug, 0) if best_slug else 0

        if best_slug and best_disc_score > 0:
            # Strongly boost the best variant
            detection.slug_scores[best_slug] += best_disc_score
            # Penalize other variants (but don't remove — broad-first)
            for slug in slugs:
                if slug != best_slug:
                    detection.slug_scores[slug] = max(
                        detection.slug_scores.get(slug, 0) - 2.0,
                        0.5,  # Keep minimum for broad search
                    )

    return detection


def get_search_filter(
    detection: ScopeDetection,
    *,
    broad: bool = True,
) -> dict:
    """Retorna filtros para a busca baseados na detecção de escopo.

    Se broad=True (padrão), não filtra fontes — apenas fornece boosting.
    Se broad=False, restringe a busca às fontes detectadas.
    """
    if broad or not detection.source_slugs:
        return {"filter_slugs": None, "boost": detection.slug_scores}
    return {"filter_slugs": detection.source_slugs, "boost": detection.slug_scores}
