"""Registro canônico das 15 fontes de conhecimento do Tutor NR.

Cada fonte corresponde a um arquivo ``extracted-text.md`` privado,
armazenado no storage S3/Tebi sob namespace tenant-aware.

Este registro é a fonte da verdade para:
- mapeamento slug → NR/variante/título;
- detecção de escopo (scope detection);
- validação de cobertura (15/15 fontes esperadas).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class KnowledgeSource:
    slug: str
    nr_code: str
    course_variant: str
    title: str
    # Termos que indicam esta fonte (para scope detection)
    scope_terms: tuple[str, ...] = field(default_factory=tuple)
    # Termos que DISTINGUEM esta fonte de outras do mesmo NR
    discriminator_terms: tuple[str, ...] = field(default_factory=tuple)


# As 15 fontes obrigatórias
SOURCES: tuple[KnowledgeSource, ...] = (
    KnowledgeSource(
        slug="nr01",
        nr_code="NR-01",
        course_variant="",
        title="NR-01 — Disposições Gerais e Gerenciamento de Riscos Ocupacionais",
        scope_terms=("nr01", "nr-01", "gro", "pgr", "gerenciamento de riscos",
                     "disposições gerais", "gerenciamento de riscos ocupacionais"),
    ),
    KnowledgeSource(
        slug="nr06",
        nr_code="NR-06",
        course_variant="",
        title="NR-06 — Equipamento de Proteção Individual (EPI)",
        scope_terms=("nr06", "nr-06", "epi", "equipamento de proteção individual",
                     "certificado de aprovação", "ca ", "capacete", "luva", "óculos",
                     "protetor auricular", "respirador"),
    ),
    KnowledgeSource(
        slug="nr10-basico",
        nr_code="NR-10",
        course_variant="Básico",
        title="NR-10 Básico — Segurança em Instalações e Serviços em Eletricidade",
        scope_terms=("nr10", "nr-10", "eletricidade", "choque elétrico",
                     "desenergização", "prontuário", "bloqueio elétrico",
                     "segurança em instalações", "serviços em eletricidade"),
        discriminator_terms=("básico", "basico", "segurança em instalações"),
    ),
    KnowledgeSource(
        slug="nr10-sep",
        nr_code="NR-10",
        course_variant="SEP",
        title="NR-10 SEP — Sistema Elétrico de Potência",
        scope_terms=("sep", "sistema elétrico de potência", "alta tensão",
                     "linha de transmissão", "subestação"),
        discriminator_terms=("sep", "sistema elétrico de potência", "alta tensão"),
    ),
    KnowledgeSource(
        slug="nr11-empilhadeira",
        nr_code="NR-11",
        course_variant="Empilhadeira",
        title="NR-11 — Empilhadeira",
        scope_terms=("empilhadeira", "forklift", "palete"),
        discriminator_terms=("empilhadeira", "forklift"),
    ),
    KnowledgeSource(
        slug="nr11-guindauto",
        nr_code="NR-11",
        course_variant="Guindauto",
        title="NR-11 — Guindauto",
        scope_terms=("guindauto", "guindaste", "munck", "caminhão munck",
                     "caminhao munck", "pluma"),
        discriminator_terms=("guindauto", "guindaste", "munck", "pluma"),
    ),
    KnowledgeSource(
        slug="nr11-minicarregadeira",
        nr_code="NR-11",
        course_variant="Minicarregadeira",
        title="NR-11 — Minicarregadeira",
        scope_terms=("minicarregadeira", "mini carregadeira", "bobcat",
                     "carregadeira compacta"),
        discriminator_terms=("minicarregadeira", "bobcat", "carregadeira compacta"),
    ),
    KnowledgeSource(
        slug="nr11-plataforma",
        nr_code="NR-11",
        course_variant="Plataforma Elevatória",
        title="NR-11 — Plataforma Elevatória",
        scope_terms=("plataforma elevatória", "plataforma elevatoria",
                     "cesta elevatória", "cesta aerea", "cesta aérea"),
        discriminator_terms=("plataforma elevatória", "cesta elevatória", "cesta aerea"),
    ),
    KnowledgeSource(
        slug="nr11-ponte",
        nr_code="NR-11",
        course_variant="Ponte Rolante",
        title="NR-11 — Ponte Rolante",
        scope_terms=("ponte rolante", "talha", "guincho", "pórtico", "portico"),
        discriminator_terms=("ponte rolante", "talha", "guincho", "pórtico"),
    ),
    KnowledgeSource(
        slug="nr11-retroescavadeira",
        nr_code="NR-11",
        course_variant="Retroescavadeira",
        title="NR-11 — Retroescavadeira",
        scope_terms=("retroescavadeira", "retro escavadeira", "escavadeira",
                     "caçamba", "cacamba", "trator"),
        discriminator_terms=("retroescavadeira", "retro escavadeira", "escavadeira"),
    ),
    KnowledgeSource(
        slug="nr12",
        nr_code="NR-12",
        course_variant="",
        title="NR-12 — Segurança no Trabalho em Máquinas e Equipamentos",
        scope_terms=("nr12", "nr-12", "máquina", "maquina", "equipamento",
                     "proteção de máquina", "parada de emergência",
                     "segurança em máquinas", "segurança em maquinas"),
    ),
    KnowledgeSource(
        slug="nr18",
        nr_code="NR-18",
        course_variant="",
        title="NR-18 — Segurança e Saúde no Trabalho na Indústria da Construção",
        scope_terms=("nr18", "nr-18", "construção civil", "construcao civil",
                     "obra", "andaime", "escavação", "escavacao", "canteiro",
                     "demolição", "demolicao", "indústria da construção"),
    ),
    KnowledgeSource(
        slug="nr33-autorizado",
        nr_code="NR-33",
        course_variant="Trabalhador Autorizado",
        title="NR-33 — Trabalhador Autorizado em Espaços Confinados",
        scope_terms=("espaço confinado", "espaco confinado", "nr33", "nr-33",
                     "pet", "permissão de entrada", "permissao de entrada",
                     "atmosfera", "vigia"),
        discriminator_terms=("trabalhador autorizado", "autorizado", "vigia"),
    ),
    KnowledgeSource(
        slug="nr33-supervisor",
        nr_code="NR-33",
        course_variant="Supervisor",
        title="NR-33 — Supervisor de Entrada em Espaços Confinados",
        scope_terms=("espaço confinado", "espaco confinado", "nr33", "nr-33",
                     "supervisor de entrada", "supervisor"),
        discriminator_terms=("supervisor", "supervisor de entrada"),
    ),
    KnowledgeSource(
        slug="nr35",
        nr_code="NR-35",
        course_variant="",
        title="NR-35 — Trabalho em Altura",
        scope_terms=("nr35", "nr-35", "trabalho em altura", "altura",
                     "queda", "cinto", "talabarte", "ancoragem", "linha de vida",
                     "resgate", "2 metros", "dois metros"),
    ),
)

# Index for fast lookup
SOURCES_BY_SLUG: dict[str, KnowledgeSource] = {s.slug: s for s in SOURCES}
SOURCES_BY_NR: dict[str, list[KnowledgeSource]] = {}
for _s in SOURCES:
    SOURCES_BY_NR.setdefault(_s.nr_code, []).append(_s)

# All expected slugs (for coverage validation)
EXPECTED_SLUGS: tuple[str, ...] = tuple(s.slug for s in SOURCES)


def get_source(slug: str) -> KnowledgeSource | None:
    return SOURCES_BY_SLUG.get(slug)


def get_sources_by_nr(nr_code: str) -> list[KnowledgeSource]:
    return SOURCES_BY_NR.get(nr_code, [])
