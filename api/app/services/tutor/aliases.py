"""Aliases e sinônimos semânticos para o Tutor NR.

Camada pequena e auditável que expande termos do usuário para melhorar
o retrieval, sem gerar respostas. Usada para:

- expandir siglas (CA → certificado de aprovação);
- mapear nomes populares (munck → guindauto);
- normalizar referências (altura → trabalho em altura).

Os aliases são aplicados na expansão da query antes do FTS, aumentando
o recall sem alterar o significado da pergunta.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


def _normalize(text: str) -> str:
    """Normaliza texto: remove acentos, lowercase."""
    nfkd = unicodedata.normalize('NFD', text)
    no_accents = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return no_accents.lower().strip()


@dataclass(frozen=True)
class AliasEntry:
    """Um alias semântico.

    trigger: termo que aparece na pergunta do usuário (normalizado)
    expansions: termos adicionais a incluir na busca
    """
    trigger: str
    expansions: tuple[str, ...] = field(default_factory=tuple)


# Aliases canônicos — auditáveis e pequenos
ALIASES: tuple[AliasEntry, ...] = (
    # Siglas → expansão
    AliasEntry("ca", ("certificado de aprovacao", "certificado de aprovação")),
    AliasEntry("sep", ("sistema eletrico de potencia", "sistema elétrico de potência")),
    AliasEntry("epi", ("equipamento de protecao individual", "equipamento de proteção individual")),
    AliasEntry("pgr", ("programa de gerenciamento de riscos",)),
    AliasEntry("gro", ("gerenciamento de riscos ocupacionais",)),
    AliasEntry("pet", ("permissao de entrada e trabalho", "permissão de entrada e trabalho")),

    # Nomes populares → termos técnicos
    AliasEntry("munck", ("guindauto", "caminhao munck", "caminhão munck")),
    AliasEntry("guindaste", ("guindauto",)),
    AliasEntry("pluma", ("guindauto",)),
    AliasEntry("bobcat", ("minicarregadeira",)),
    AliasEntry("cesta aerea", ("plataforma elevatoria", "plataforma elevatória")),
    AliasEntry("cesta elevatoria", ("plataforma elevatoria", "plataforma elevatória")),

    # Referências abreviadas → termos completos
    AliasEntry("altura", ("trabalho em altura",)),
    AliasEntry("espanco confinado", ("espaco confinado", "espaço confinado")),
    AliasEntry("confinado", ("espaco confinado", "espaço confinado")),
    AliasEntry("eletricidade", ("seguranca em instalacoes eletricas", "segurança em instalações elétricas")),

    # Termos NR-33
    AliasEntry("vigia", ("trabalhador autorizado", "espaco confinado", "espaço confinado")),
    AliasEntry("supervisor de entrada", ("supervisor", "espaco confinado", "espaço confinado")),
)


def expand_query(question: str) -> str:
    """Expande a pergunta com aliases semânticos.

    Retorna a pergunta original + termos expandidos concatenados,
    para uso na query de FTS. Não altera a pergunta original exibida
    ao usuário.

    Exemplo:
        "para que serve o CA do EPI?"
        → "para que serve o CA do EPI? certificado de aprovação equipamento de proteção individual"
    """
    normalized = _normalize(question)
    # Tokenize para matching de palavras isoladas (evita match parcial)
    tokens = set(re.findall(r'\b\w+\b', normalized))

    additions: list[str] = []
    for alias in ALIASES:
        norm_trigger = _normalize(alias.trigger)
        # Para triggers de palavra única, exige match de token completo
        if ' ' not in norm_trigger:
            if norm_trigger in tokens:
                additions.extend(alias.expansions)
        else:
            # Para triggers multi-palavra, verifica substring
            if norm_trigger in normalized:
                additions.extend(alias.expansions)

    if additions:
        return question + ' ' + ' '.join(additions)
    return question
