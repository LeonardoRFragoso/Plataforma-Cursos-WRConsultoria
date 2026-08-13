"""Utilitários pequenos usados em toda a aplicação."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Retorna a data/hora atual em UTC sem informação de timezone."""
    return datetime.now(UTC).replace(tzinfo=None)
