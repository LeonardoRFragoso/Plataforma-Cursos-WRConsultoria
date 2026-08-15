"""Testa endpoints de health: /health/live e /health/ready."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import InterfaceError, OperationalError

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


@pytest.mark.asyncio
async def test_health_live_has_no_db_query(monkeypatch):
    """/health/live nunca toca no banco mesmo quando o DB está indisponível."""
    from app import main as app_main

    async def _boom(*args, **kwargs):
        raise OperationalError("SELECT 1", params=None, orig=Exception("no db"))

    monkeypatch.setattr(app_main.AsyncSessionLocal, "__call__", _boom)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_ready_503_when_db_unavailable(monkeypatch):
    """Readiness retorna 503 not_ready quando o DB levanta OperationalError.

    O probe usa uma sessão dedicada dentro do try, então a falha de
    conectividade é capturada e mapeada para 503 em vez de um 500 não
    controlado (que aconteceria se a dependência get_db falhasse antes do
    handler).
    """
    from app import main as app_main

    class _FailingSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, *args, **kwargs):
            raise OperationalError(
                "SELECT 1", params=None, orig=ConnectionError("db down")
            )

    monkeypatch.setattr(app_main, "AsyncSessionLocal", lambda: _FailingSession())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert "error" in body


@pytest.mark.asyncio
async def test_health_ready_503_on_interface_error(monkeypatch):
    """Readiness retorna 503 not_ready para InterfaceError (outra falha de DB)."""
    from app import main as app_main

    class _FailingSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, *args, **kwargs):
            raise InterfaceError(
                "SELECT 1", params=None, orig=ConnectionError("interface down")
            )

    monkeypatch.setattr(app_main, "AsyncSessionLocal", lambda: _FailingSession())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


@pytest.mark.asyncio
async def test_health_ready_503_on_oserror(monkeypatch):
    """Readiness retorna 503 not_ready para OSError (falha de socket de baixo nível)."""
    from app import main as app_main

    class _FailingSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, *args, **kwargs):
            raise OSError("connection refused")

    monkeypatch.setattr(app_main, "AsyncSessionLocal", lambda: _FailingSession())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


@pytest.mark.asyncio
async def test_health_ready_response_has_no_secrets():
    """Resposta de readiness não vaza URL do banco nem chaves/secretos."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/ready")
    body_text = response.text.lower()
    assert "database_url" not in body_text
    assert "secret_key" not in body_text
    assert "password" not in body_text
    assert "postgresql+asyncpg" not in body_text


@pytest.mark.asyncio
async def test_health_ready_503_response_has_no_secrets(monkeypatch):
    """Resposta 503 de readiness também não vaza detalhes sensíveis."""
    from app import main as app_main

    sensitive = "postgresql+asyncpg://user:supersecret@host:5432/db"

    class _FailingSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, *args, **kwargs):
            raise OperationalError(
                "SELECT 1", params=None, orig=ConnectionError(sensitive)
            )

    monkeypatch.setattr(app_main, "AsyncSessionLocal", lambda: _FailingSession())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/ready")
    assert response.status_code == 503
    body_text = response.text.lower()
    assert "supersecret" not in body_text
    assert "postgresql+asyncpg" not in body_text
    assert "password" not in body_text
