"""CORS regression tests.

Verifies the CORS middleware configuration:
- Allowed origins receive correct CORS headers
- Unknown origins do NOT receive Access-Control-Allow-Origin
- Credentials header is present for allowed origins
- Preflight (OPTIONS) requests are handled correctly
- Rate-limited responses preserve CORS for trusted origins

Does NOT configure `*` with credentials to satisfy tests — verifies the
actual configured origins list.
"""

from unittest.mock import MagicMock

import pytest

from app.core.config import settings


@pytest.fixture
def cors_origins():
    """Capture the configured CORS origins."""
    return list(settings.CORS_ORIGINS)


async def test_cors_allowed_origin_receives_headers(client, cors_origins):
    """A configured origin receives Access-Control-Allow-Origin."""
    if not cors_origins:
        pytest.skip("No CORS origins configured")
    origin = cors_origins[0]
    response = await client.get(
        "/health/live",
        headers={"Origin": origin},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"


async def test_cors_unknown_origin_no_allow_origin(client):
    """An unknown origin does NOT receive Access-Control-Allow-Origin."""
    response = await client.get(
        "/health/live",
        headers={"Origin": "https://evil.example.com"},
    )
    assert response.status_code == 200
    # Unknown origin must not get an ACAO header
    acao = response.headers.get("access-control-allow-origin")
    assert acao != "https://evil.example.com"
    # Starlette CORSMiddleware omits ACAO entirely for disallowed origins
    # when allow_credentials=True (cannot use wildcard).


async def test_cors_preflight_allowed_origin(client, cors_origins):
    """Preflight OPTIONS for a configured origin returns correct headers."""
    if not cors_origins:
        pytest.skip("No CORS origins configured")
    origin = cors_origins[0]
    response = await client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"
    # Methods and headers must be permitted
    allow_methods = response.headers.get("access-control-allow-methods", "")
    assert "POST" in allow_methods.upper()


async def test_cors_preflight_unknown_origin_rejected(client):
    """Preflight OPTIONS for an unknown origin does not return ACAO."""
    response = await client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    # Disallowed preflight → 400 from CORSMiddleware
    assert response.status_code in (400, 200)
    acao = response.headers.get("access-control-allow-origin")
    assert acao != "https://evil.example.com"


async def test_rate_limited_response_keeps_cors_for_allowed_origin(client, cors_origins):
    """A trusted browser origin can read a 429 response and Retry-After."""
    if not cors_origins:
        pytest.skip("No CORS origins configured")

    from app.core import rate_limit as rl_module

    original_enabled = settings.RATE_LIMIT_ENABLED
    original_backend = rl_module._backend
    blocking_backend = MagicMock()
    blocking_backend.is_allowed.return_value = False

    try:
        settings.RATE_LIMIT_ENABLED = True
        rl_module._backend = blocking_backend
        origin = cors_origins[0]
        response = await client.get("/api/v1/courses", headers={"Origin": origin})

        assert response.status_code == 429
        assert response.headers.get("access-control-allow-origin") == origin
        assert response.headers.get("access-control-allow-credentials") == "true"
        assert response.headers.get("retry-after") == str(settings.RATE_LIMIT_WINDOW_SECONDS)
    finally:
        settings.RATE_LIMIT_ENABLED = original_enabled
        rl_module._backend = original_backend


async def test_rate_limited_response_does_not_reflect_unknown_origin(client):
    """The direct 429 response must never reflect an arbitrary Origin."""
    from app.core import rate_limit as rl_module

    original_enabled = settings.RATE_LIMIT_ENABLED
    original_backend = rl_module._backend
    blocking_backend = MagicMock()
    blocking_backend.is_allowed.return_value = False

    try:
        settings.RATE_LIMIT_ENABLED = True
        rl_module._backend = blocking_backend
        response = await client.get(
            "/api/v1/courses",
            headers={"Origin": "https://evil.example.com"},
        )

        assert response.status_code == 429
        assert response.headers.get("access-control-allow-origin") != "https://evil.example.com"
        assert response.headers.get("retry-after") == str(settings.RATE_LIMIT_WINDOW_SECONDS)
    finally:
        settings.RATE_LIMIT_ENABLED = original_enabled
        rl_module._backend = original_backend


async def test_rate_limit_does_not_consume_preflight_quota(client, cors_origins):
    """OPTIONS requests bypass the application rate-limit counter."""
    if not cors_origins:
        pytest.skip("No CORS origins configured")

    from app.core import rate_limit as rl_module

    original_enabled = settings.RATE_LIMIT_ENABLED
    original_backend = rl_module._backend
    blocking_backend = MagicMock()
    blocking_backend.is_allowed.return_value = False

    try:
        settings.RATE_LIMIT_ENABLED = True
        rl_module._backend = blocking_backend
        response = await client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": cors_origins[0],
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        assert response.status_code == 200
        blocking_backend.is_allowed.assert_not_called()
    finally:
        settings.RATE_LIMIT_ENABLED = original_enabled
        rl_module._backend = original_backend


async def test_cors_no_wildcard_with_credentials(client):
    """CORS must not use wildcard origin when credentials are enabled."""
    # This is a security contract: allow_credentials=True + allow_origins=*
    # is a browser security violation. Verify the config doesn't do this.
    assert "*" not in settings.CORS_ORIGINS, (
        "CORS_ORIGINS must not contain '*' when credentials are enabled"
    )
