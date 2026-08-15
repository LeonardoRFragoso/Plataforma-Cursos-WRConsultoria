"""Testa endpoints de health: /health/live e /health/ready."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_live():
    """Liveness probe retorna 200 sem checar dependências."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_ready():
    """Readiness probe retorna 200 e checa DB."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "db_latency_ms" in response.json()


@pytest.mark.asyncio
async def test_health_legacy_still_works():
    """Endpoint /health original ainda funciona (backward compat)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
