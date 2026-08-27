"""Chunking orientado por estrutura Markdown para o Tutor NR.

Quebra os ``extracted-text.md`` em chunks preservando o contexto
hierárquico (heading_path). Cada chunk é compreensível isoladamente.

Estratégia:
- Detecta headings ``#``, ``##``, ``###`` etc.;
- Agrupa conteúdo sob cada heading;
- Se um bloco exceder ~1200 tokens aprox., subdivide por parágrafos;
- Pequeno overlap entre sub-chunks de um mesmo bloco;
- Remove ruído de OCR (números de página isolados, headers repetitivos).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

# Approximate token estimate: ~4 chars per token for Portuguese
_CHARS_PER_TOKEN = 4
_MIN_CHUNK_CHARS = 200
_MAX_CHUNK_CHARS = 4800  # ~1200 tokens
_OVERLAP_CHARS = 200

# Patterns for OCR noise removal
_PAGE_MARKER_RE = re.compile(r'^##\s+PÁGINA\s+\d+\s*$', re.IGNORECASE | re.MULTILINE)
_ISOLATED_PAGE_NUM_RE = re.compile(r'^\s*\d{1,4}\s*$', re.MULTILINE)
# Repeated header/footer noise (e.g. "WRCONSULTORIAESOLUCOESEMQSMS")
_NOISE_RE = re.compile(
    r'(?:WR\s*CONSULTORIA\s*E\s*SOLUCOES\s*EM\s*QSMS|'
    r'WRCONSULTORIAESOLUCOESEMQSMS)',
    re.IGNORECASE,
)
# Multiple blank lines
_MULTI_BLANK_RE = re.compile(r'\n{3,}')


@dataclass
class Chunk:
    chunk_index: int
    heading: str | None
    heading_path: str | None
    content: str
    content_hash: str
    metadata: dict = field(default_factory=dict)


def _clean_text(text: str) -> str:
    """Remove ruído de OCR sem alterar significado técnico."""
    # Remove page markers but keep a lightweight separator
    text = _PAGE_MARKER_RE.sub('', text)
    # Remove isolated page numbers (likely OCR artifacts)
    text = _ISOLATED_PAGE_NUM_RE.sub('', text)
    # Remove repeated brand noise
    text = _NOISE_RE.sub('', text)
    # Collapse multiple blank lines
    text = _MULTI_BLANK_RE.sub('\n\n', text)
    # Strip trailing whitespace per line
    lines = [line.rstrip() for line in text.split('\n')]
    text = '\n'.join(lines)
    return text.strip()


def _parse_heading_level(line: str) -> int | None:
    """Retorna o nível do heading (1-6) ou None se não for heading."""
    match = re.match(r'^(#{1,6})\s+(.+)$', line)
    if match:
        return len(match.group(1))
    return None


def _split_into_blocks(text: str) -> list[tuple[list[str], str]]:
    """Divide o texto em blocos por heading.

    Retorna lista de (heading_path, content) onde heading_path é a
    hierarquia de headings até aquele ponto.
    """
    lines = text.split('\n')
    blocks: list[tuple[list[str], str]] = []
    current_heading_stack: list[tuple[int, str]] = []
    current_lines: list[str] = []

    def flush():
        content = '\n'.join(current_lines).strip()
        if content:
            path = [h for _, h in current_heading_stack]
            blocks.append((path, content))
        current_lines.clear()

    for line in lines:
        level = _parse_heading_level(line)
        if level is not None:
            flush()
            heading_text = re.sub(r'^#+\s+', '', line).strip()
            # Pop stack until we're at a lower level
            while current_heading_stack and current_heading_stack[-1][0] >= level:
                current_heading_stack.pop()
            current_heading_stack.append((level, heading_text))
        else:
            current_lines.append(line)

    flush()
    return blocks


def _subdivide_content(content: str, heading_path: list[str]) -> list[str]:
    """Subdivide conteúdo muito longo em partes com overlap."""
    if len(content) <= _MAX_CHUNK_CHARS:
        return [content]

    parts: list[str] = []
    paragraphs = re.split(r'\n\n+', content)
    current = ''

    for para in paragraphs:
        if len(current) + len(para) + 2 > _MAX_CHUNK_CHARS and current:
            parts.append(current.strip())
            # Overlap: start new chunk with last paragraph
            if len(current) > _OVERLAP_CHARS:
                overlap_text = current[-_OVERLAP_CHARS:]
                # Try to start at a paragraph boundary
                boundary = overlap_text.find('\n\n')
                if boundary >= 0:
                    current = overlap_text[boundary + 2:]
                else:
                    current = ''
            else:
                current = ''
        current = current + '\n\n' + para if current else para

    if current.strip():
        parts.append(current.strip())

    # Ensure minimum size by merging tiny trailing parts
    if len(parts) >= 2 and len(parts[-1]) < _MIN_CHUNK_CHARS:
        parts[-2] = parts[-2] + '\n\n' + parts[-1]
        parts.pop()

    return parts if parts else [content]


def chunk_document(text: str, source_title: str = "") -> list[Chunk]:
    """Fragmenta um documento Markdown em chunks estruturados.

    Args:
        text: conteúdo Markdown bruto do extracted-text.md
        source_title: título da fonte (usado como heading raiz se ausente)

    Returns:
        Lista de Chunk com heading_path, content e content_hash
    """
    cleaned = _clean_text(text)
    if not cleaned:
        return []

    # Prepend source title as H1 if the document doesn't start with one
    if source_title and not cleaned.startswith('#'):
        cleaned = f"# {source_title}\n\n{cleaned}"

    blocks = _split_into_blocks(cleaned)
    chunks: list[Chunk] = []
    idx = 0

    for heading_path, content in blocks:
        if not content.strip():
            continue

        heading = heading_path[-1] if heading_path else None
        path_str = ' > '.join(heading_path) if heading_path else None

        sub_parts = _subdivide_content(content, heading_path)
        for part in sub_parts:
            if len(part.strip()) < _MIN_CHUNK_CHARS and chunks:
                # Merge tiny fragment into previous chunk
                chunks[-1].content = chunks[-1].content + '\n\n' + part.strip()
                chunks[-1].content_hash = _hash_chunk(chunks[-1].content)
                continue

            chunk = Chunk(
                chunk_index=idx,
                heading=heading,
                heading_path=path_str,
                content=part.strip(),
                content_hash=_hash_chunk(part),
                metadata={
                    "char_count": len(part.strip()),
                    "heading_depth": len(heading_path),
                },
            )
            chunks.append(chunk)
            idx += 1

    return chunks


def _hash_chunk(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()
