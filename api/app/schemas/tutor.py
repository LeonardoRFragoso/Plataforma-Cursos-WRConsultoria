"""Schemas do Tutor NR (endpoint /api/v1/tutor/ask)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TutorMessageContext(BaseModel):
    """Mensagem anterior no contexto da conversa."""
    role: str = Field(..., description="user | assistant")
    text: str = Field(..., max_length=2000)


class TutorAskRequest(BaseModel):
    """Payload do POST /api/v1/tutor/ask."""
    question: str = Field(..., min_length=1, max_length=1000)
    conversation_context: list[TutorMessageContext] = Field(
        default_factory=list, max_length=20,
    )


class TutorSource(BaseModel):
    """Fonte consultada (informação amigável, sem dados internos)."""
    label: str
    nr_code: str
    variant: str = ""
    heading: str = ""


class TutorAskResponse(BaseModel):
    """Resposta do Tutor NR."""
    answer: str
    sources: list[TutorSource] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    confidence: str = Field(..., description="HIGH | MEDIUM | LOW")
    scope: list[str] = Field(default_factory=list)
    knowledge_level: str = Field(
        ..., description="DEEP_KNOWLEDGE | GENERAL_KNOWLEDGE | NO_CONFIDENT_SOURCE"
    )


class TutorCoverageSource(BaseModel):
    """Status de cobertura de uma fonte."""
    slug: str
    nr_code: str
    course_variant: str
    title: str
    status: str = Field(..., description="indexed | missing")
    char_count: int = 0
    chunk_count: int = 0
    heading_count: int = 0
    content_hash: str = ""


class TutorCoverageResponse(BaseModel):
    """Resposta do endpoint de cobertura."""
    total_expected: int
    total_indexed: int
    total_chunks: int
    sources: list[TutorCoverageSource]
    all_covered: bool
