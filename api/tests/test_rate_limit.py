from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.core.rate_limit import (
    MemoryBackend,
    RateLimiter,
    RedisBackend,
    get_rate_limiter,
    reset_rate_limiter,
)


def test_rate_limiter_allows_within_limit():
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    assert limiter.is_allowed("ip-1", datetime.now(UTC)) is True
    assert limiter.is_allowed("ip-1", datetime.now(UTC)) is True
    assert limiter.is_allowed("ip-1", datetime.now(UTC)) is True


def test_rate_limiter_blocks_over_limit():
    now = datetime.now(UTC)
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    assert limiter.is_allowed("ip-1", now) is True
    assert limiter.is_allowed("ip-1", now + timedelta(seconds=1)) is True
    assert limiter.is_allowed("ip-1", now + timedelta(seconds=2)) is False


def test_rate_limiter_resets_after_window():
    now = datetime.now(UTC)
    limiter = RateLimiter(max_requests=1, window_seconds=1)
    assert limiter.is_allowed("ip-1", now) is True
    assert limiter.is_allowed("ip-1", now + timedelta(seconds=0.5)) is False
    assert limiter.is_allowed("ip-1", now + timedelta(seconds=2)) is True


# ---- Backend abstraction ----


def test_memory_backend_isolates_keys():
    backend = MemoryBackend()
    assert backend.is_allowed("a", 1, 60, datetime.now(UTC)) is True
    assert backend.is_allowed("a", 1, 60, datetime.now(UTC)) is False
    # Chave diferente tem seu próprio contador
    assert backend.is_allowed("b", 1, 60, datetime.now(UTC)) is True


def test_memory_backend_window_expiry():
    now = datetime.now(UTC)
    backend = MemoryBackend()
    assert backend.is_allowed("k", 1, 1, now) is True
    assert backend.is_allowed("k", 1, 1, now + timedelta(seconds=0.5)) is False
    assert backend.is_allowed("k", 1, 1, now + timedelta(seconds=2)) is True


def test_redis_backend_allows_under_limit():
    """RedisBackend usa INCR + EXPIRE; mockamos o pipeline."""
    backend = RedisBackend.__new__(RedisBackend)
    mock_redis = MagicMock()
    pipe = MagicMock()
    pipe.execute.return_value = [1, True]
    mock_redis.pipeline.return_value = pipe
    backend._redis = mock_redis

    assert backend.is_allowed("ip-1", 5, 60) is True
    pipe.incr.assert_called_once_with("ratelimit:ip-1")
    pipe.expire.assert_called_once_with("ratelimit:ip-1", 60)


def test_redis_backend_blocks_over_limit():
    backend = RedisBackend.__new__(RedisBackend)
    mock_redis = MagicMock()
    pipe = MagicMock()
    pipe.execute.return_value = [6, True]  # 6 > max 5
    mock_redis.pipeline.return_value = pipe
    backend._redis = mock_redis

    assert backend.is_allowed("ip-1", 5, 60) is False


def test_get_rate_limiter_defaults_to_memory():
    reset_rate_limiter()
    with patch("app.core.rate_limit.settings") as mock_settings:
        mock_settings.RATE_LIMIT_REDIS_URL = ""
        backend = get_rate_limiter()
        assert isinstance(backend, MemoryBackend)
    reset_rate_limiter()


def test_get_rate_limiter_uses_redis_when_configured():
    reset_rate_limiter()
    with patch("app.core.rate_limit.settings") as mock_settings:
        mock_settings.RATE_LIMIT_REDIS_URL = "redis://localhost:6379/0"
        with patch("redis.Redis.from_url") as mock_from_url:
            mock_from_url.return_value = MagicMock()
            backend = get_rate_limiter()
            assert isinstance(backend, RedisBackend)
            mock_from_url.assert_called_once_with(
                "redis://localhost:6379/0", decode_responses=True
            )
    reset_rate_limiter()


def test_get_rate_limiter_singleton():
    reset_rate_limiter()
    with patch("app.core.rate_limit.settings") as mock_settings:
        mock_settings.RATE_LIMIT_REDIS_URL = ""
        a = get_rate_limiter()
        b = get_rate_limiter()
        assert a is b
    reset_rate_limiter()


def test_rate_limiter_delegates_to_backend():
    mock_backend = MagicMock()
    mock_backend.is_allowed.return_value = True
    limiter = RateLimiter(max_requests=10, window_seconds=30, backend=mock_backend)
    assert limiter.is_allowed("key") is True
    mock_backend.is_allowed.assert_called_once()
    args = mock_backend.is_allowed.call_args
    assert args.args[0] == "key"
    assert args.args[1] == 10
    assert args.args[2] == 30


# ---- Middleware integration ----


@pytest.mark.asyncio
async def test_middleware_uses_factory_backend_not_global_limiter(client):
    """O middleware usa get_rate_limiter(), não o limiter global.

    Com RATE_LIMIT_ENABLED=True e um backend mockado que bloqueia,
    o middleware deve retornar 429 usando o backend da factory.
    """
    from app.core import rate_limit as rl_module
    from app.core.config import settings as app_settings

    # Salva estado original
    original_enabled = app_settings.RATE_LIMIT_ENABLED
    original_backend = rl_module._backend
    rl_module._backend = None

    blocking_backend = MagicMock()
    blocking_backend.is_allowed.return_value = False

    try:
        app_settings.RATE_LIMIT_ENABLED = True
        rl_module._backend = blocking_backend

        response = await client.get("/api/v1/courses")
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.json()["detail"]

        # Prova que o backend da factory foi chamado, não o limiter global
        blocking_backend.is_allowed.assert_called()
        call_args = blocking_backend.is_allowed.call_args
        assert call_args.args[1] == app_settings.RATE_LIMIT_REQUESTS
        assert call_args.args[2] == app_settings.RATE_LIMIT_WINDOW_SECONDS
    finally:
        app_settings.RATE_LIMIT_ENABLED = original_enabled
        rl_module._backend = original_backend


@pytest.mark.asyncio
async def test_middleware_redis_backend_used_when_configured(client):
    """Com RATE_LIMIT_REDIS_URL definida, o middleware usa RedisBackend."""
    from app.core import rate_limit as rl_module
    from app.core.config import settings as app_settings

    original_enabled = app_settings.RATE_LIMIT_ENABLED
    original_redis_url = app_settings.RATE_LIMIT_REDIS_URL
    original_backend = rl_module._backend

    try:
        app_settings.RATE_LIMIT_ENABLED = True
        app_settings.RATE_LIMIT_REDIS_URL = "redis://localhost:6379/0"
        rl_module._backend = None

        with patch("redis.Redis.from_url") as mock_from_url:
            mock_redis = MagicMock()
            pipe = MagicMock()
            pipe.execute.return_value = [1, True]
            mock_redis.pipeline.return_value = pipe
            mock_from_url.return_value = mock_redis

            response = await client.get("/api/v1/courses")
            # Backend Redis foi instanciado e usado
            mock_from_url.assert_called_once_with(
                "redis://localhost:6379/0", decode_responses=True
            )
            # Não deve ser 429 (count=1 <= max_requests)
            assert response.status_code != 429
    finally:
        app_settings.RATE_LIMIT_ENABLED = original_enabled
        app_settings.RATE_LIMIT_REDIS_URL = original_redis_url
        rl_module._backend = original_backend
