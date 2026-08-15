import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException

from app.core import utils
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.core.storage import _get_s3_client, _key_for_lesson, generate_upload_url, generate_watch_url
from app.services import CertificateService, MercadoPagoService


def test_utc_now_returns_datetime():
    now = utils.utc_now()
    assert isinstance(now, datetime)


def test_password_hashing_roundtrip():
    password = "senha-segura-123"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True
    assert verify_password("wrong", hashed) is False


def test_access_token_roundtrip():
    token = create_access_token({"sub": str(uuid.uuid4())})
    assert isinstance(token, str)
    payload = decode_token(token)
    assert "sub" in payload


def test_decode_token_rejects_invalid_token():
    with pytest.raises(HTTPException):
        decode_token("not-a-valid-token")


def test_certificate_service_generates_pdf():
    pdf = CertificateService.generate_certificate_pdf(
        student_name="Aluno Teste",
        course_name="Curso Teste",
        course_code="CT-01",
        carga_horaria=40,
        certificate_number="CERT-123",
        validation_code="VAL-123",
        responsible_admin_name="Responsável Teste",
        brand_name="Marca Teste",
        validation_url="https://example.com/validate",
    )
    assert isinstance(pdf, bytes)
    assert len(pdf) > 0


def test_certificate_service_with_issued_date():
    pdf = CertificateService.generate_certificate_pdf(
        student_name="Aluno Teste",
        course_name="Curso Teste",
        course_code="CT-01",
        carga_horaria=40,
        certificate_number="CERT-123",
        validation_code="VAL-123",
        responsible_admin_name="Responsável Teste",
        brand_name="Marca Teste",
        validation_url="https://example.com/validate",
        issued_date=datetime(2024, 1, 1, tzinfo=UTC),
    )
    assert isinstance(pdf, bytes)


@pytest.mark.asyncio
async def test_mercado_pago_create_preference(monkeypatch):
    response_data = {
        "id": "PREF-123",
        "init_point": "https://mp.init",
        "sandbox_init_point": "https://mp.sandbox",
    }

    class FakeResponse:
        status_code = 201
        text = "{}"

        def json(self):
            return response_data

    class FakeClient:
        async def post(self, *args, **kwargs):
            return FakeResponse()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: FakeClient())
    service = MercadoPagoService()
    result = await service.create_preference("teste", 100.0, "aluno@teste.com", "Curso")
    assert result["id"] == "PREF-123"


@pytest.mark.asyncio
async def test_mercado_pago_get_payment(monkeypatch):
    response_data = {"id": "PAY-123", "status": "approved"}

    class FakeResponse:
        status_code = 200
        text = "{}"

        def json(self):
            return response_data

    class FakeClient:
        async def get(self, *args, **kwargs):
            return FakeResponse()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: FakeClient())
    service = MercadoPagoService()
    result = await service.get_payment_info("PAY-123")
    assert result["status"] == "approved"


@pytest.mark.asyncio
async def test_mercado_pago_refund(monkeypatch):
    response_data = {"id": "REF-123", "status": "approved"}

    class FakeResponse:
        status_code = 201
        text = "{}"

        def json(self):
            return response_data

    class FakeClient:
        async def post(self, *args, **kwargs):
            return FakeResponse()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: FakeClient())
    service = MercadoPagoService()
    result = await service.refund_payment("PAY-123")
    assert result["status"] == "approved"


@pytest.mark.asyncio
async def test_mercado_pago_error():
    class FakeError(Exception):
        pass

    class FakeClient:
        async def post(self, *args, **kwargs):
            raise FakeError("boom")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    with patch("httpx.AsyncClient", return_value=FakeClient()):
        service = MercadoPagoService()
        with pytest.raises(FakeError):
            await service.create_preference("teste", 100.0, "aluno@teste.com", "Curso")


def test_key_for_lesson():
    key = _key_for_lesson(uuid.uuid4(), "aula.mp4")
    assert key.endswith("/aula.mp4")


@pytest.mark.asyncio
async def test_generate_upload_url_success(monkeypatch):
    settings_patch = {
        "STORAGE_ENDPOINT": "http://localhost:9000",
        "STORAGE_ACCESS_KEY": "key",
        "STORAGE_SECRET_KEY": "secret",
        "STORAGE_REGION": "us-east-1",
        "STORAGE_BUCKET": "bucket",
    }

    with patch("app.core.storage.settings") as mock_settings:
        for k, v in settings_patch.items():
            setattr(mock_settings, k, v)

        s3 = MagicMock()
        s3.generate_presigned_url.return_value = "http://presigned/upload"
        with patch("app.core.storage._get_s3_client", return_value=s3):
            url, key = await generate_upload_url(
                uuid.uuid4(),
                "aula.mp4",
                content_type="video/mp4",
                content_length=1024,
            )
            assert url == "http://presigned/upload"
            assert key.startswith("lessons/")


@pytest.mark.asyncio
async def test_generate_upload_url_invalid_mime():
    with patch("app.core.storage.settings") as mock_settings:
        mock_settings.STORAGE_ENDPOINT = "http://localhost:9000"
        mock_settings.STORAGE_ACCESS_KEY = "key"
        mock_settings.STORAGE_SECRET_KEY = "secret"

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await generate_upload_url(uuid.uuid4(), "aula.avi", content_type="video/x-msvideo")
        assert exc.value.status_code == 415


@pytest.mark.asyncio
async def test_generate_upload_url_too_large():
    with patch("app.core.storage.settings") as mock_settings:
        mock_settings.STORAGE_ENDPOINT = "http://localhost:9000"
        mock_settings.STORAGE_ACCESS_KEY = "key"
        mock_settings.STORAGE_SECRET_KEY = "secret"

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await generate_upload_url(
                uuid.uuid4(),
                "aula.mp4",
                content_type="video/mp4",
                content_length=3 * 1024 * 1024 * 1024,
            )
        assert exc.value.status_code == 413


@pytest.mark.asyncio
async def test_generate_watch_url_client_error():
    with patch("app.core.storage.settings") as mock_settings:
        mock_settings.STORAGE_ENDPOINT = "http://localhost:9000"
        mock_settings.STORAGE_ACCESS_KEY = "key"
        mock_settings.STORAGE_SECRET_KEY = "secret"
        mock_settings.STORAGE_WATCH_URL_EXPIRATION = 3600

        s3 = MagicMock()
        s3.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "not found"}},
            "get_object",
        )

        from fastapi import HTTPException

        with patch("app.core.storage._get_s3_client", return_value=s3):
            with pytest.raises(HTTPException) as exc:
                await generate_watch_url(uuid.uuid4(), "aula.mp4")
            assert exc.value.status_code == 500


def test_get_s3_client():
    with patch("app.core.storage.settings") as mock_settings:
        mock_settings.STORAGE_ENDPOINT = "http://localhost:9000"
        mock_settings.STORAGE_ACCESS_KEY = "key"
        mock_settings.STORAGE_SECRET_KEY = "secret"
        mock_settings.STORAGE_REGION = "us-east-1"
        client = _get_s3_client()
        assert client is not None
