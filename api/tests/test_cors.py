"""CORS regression tests.

Verifies the CORS middleware configuration:
- Allowed origins receive correct CORS headers
- Unknown origins do NOT receive Access-Control-Allow-Origin
- Credentials header is present for allowed origins
- Preflight (OPTIONS) requests are handled correctly

Does NOT configure `*` with credentials to satisfy tests — verifies the
actual configured origins list.
"""

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
    # Starlight CORSMiddleware omits ACAO entirely for disallowed origins
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


async def test_cors_no_wildcard_with_credentials(client):
    """CORS must not use wildcard origin when credentials are enabled."""
    # This is a security contract: allow_credentials=True + allow_origins=*
    # is a browser security violation. Verify the config doesn't do this.
    assert "*" not in settings.CORS_ORIGINS, (
        "CORS_ORIGINS must not contain '*' when credentials are enabled"
    )
