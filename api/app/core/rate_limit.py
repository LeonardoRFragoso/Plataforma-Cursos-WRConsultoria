"""Rate limiting com abstração de backend (in-memory ou Redis).

Em produção, o backend Redis compartilha o estado entre múltiplos
workers/processos. Em desenvolvimento e testes, o backend in-memory
preserva o comportamento existente.

A fábrica ``get_rate_limiter`` seleciona o backend conforme configuração:
- RATE_LIMIT_REDIS_URL definida -> RedisBackend
- caso contrário -> MemoryBackend
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Protocol

from app.core.config import settings


class RateLimitBackend(Protocol):
    """Interface para backends de rate limiting (janela deslizante)."""

    def is_allowed(self, key: str, max_requests: int, window_seconds: int, now: datetime | None = None) -> bool: ...


class MemoryBackend:
    """Backend in-memory (desenvolvimento/testes).

    Mantém listas de timestamps por chave. Não compartilha estado entre
    processos.
    """

    def __init__(self) -> None:
        self._requests: dict[str, list[datetime]] = defaultdict(list)

    def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        now: datetime | None = None,
    ) -> bool:
        if now is None:
            now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=window_seconds)
        timestamps = [t for t in self._requests[key] if t > cutoff]
        self._requests[key] = timestamps

        if len(timestamps) >= max_requests:
            return False

        timestamps.append(now)
        return True


class RedisBackend:
    """Backend Redis (produção).

    Usa INCR + EXPIRE para um contador fixo por janela. Não é uma janela
    deslizante estrita, mas é atômico e suficiente para proteção de API.
    Requer a dependência ``redis>=4``.
    """

    def __init__(self, redis_url: str) -> None:
        import redis  # import tardio para evitar dependência em testes

        self._redis = redis.Redis.from_url(redis_url, decode_responses=True)

    def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        now: datetime | None = None,
    ) -> bool:
        redis_key = f"ratelimit:{key}"
        pipe = self._redis.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, window_seconds)
        count, _ = pipe.execute()
        return int(count) <= max_requests


_backend: RateLimitBackend | None = None


def get_rate_limiter() -> RateLimitBackend:
    """Retorna o backend configurado (singleton)."""
    global _backend
    if _backend is None:
        redis_url = getattr(settings, "RATE_LIMIT_REDIS_URL", "")
        if redis_url:
            _backend = RedisBackend(redis_url)
        else:
            _backend = MemoryBackend()
    return _backend


def reset_rate_limiter() -> None:
    """Reseta o singleton (para testes)."""
    global _backend
    _backend = None


class RateLimiter:
    """Limitador por chave com janela deslizante.

    Mantido para compatibilidade com código existente. Delega para o
    backend configurado.
    """

    def __init__(self, max_requests: int, window_seconds: int, backend: RateLimitBackend | None = None):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._backend = backend or MemoryBackend()

    def is_allowed(self, key: str, now: datetime | None = None) -> bool:
        return self._backend.is_allowed(
            key, self.max_requests, self.window_seconds, now
        )


# Instância global compatível com o código existente (in-memory).
limiter = RateLimiter(
    max_requests=settings.RATE_LIMIT_REQUESTS,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
)
