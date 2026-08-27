import hashlib
import hmac
from datetime import timedelta

import pytest

from app.core.config import settings
from app.core.utils import utc_now
from app.services.certificate_signing_provider import (
    ExternalPadesGatewayProvider,
    SigningPollResult,
    SigningProviderError,
)
from app.services.certificate_signing_service import verify_webhook_signature
from tests.test_trusted_certificate_document_pipeline import _ready_for_signature


@pytest.fixture
def local_certificate_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "STORAGE_LOCAL_DIR", str(tmp_path / "signing-storage"))
    return tmp_path


@pytest.mark.asyncio
async def test_mock_signing_queue_completes_document_without_real_icp_claim(
    client,
    admin_headers,
    local_certificate_storage,
):
    fixture = await _ready_for_signature(client, admin_headers)
    enrollment_id = fixture["enrollment"]["id"]
    prepared = await client.post(
        f"/api/v1/certificate-documents/enrollments/{enrollment_id}/prepare",
        headers=admin_headers,
    )
    assert prepared.status_code == 201, prepared.text
    certificate_id = prepared.json()["certificate_id"]

    profile = await client.put(
        "/api/v1/certificate-signing/profile",
        json={
            "provider": "MOCK",
            "enabled": True,
            "signer_display_name": "Responsável Técnico de Teste",
            "certificate_fingerprint_sha256": hashlib.sha256(b"mock:Responsável Técnico de Teste").hexdigest(),
            "certificate_not_after": (utc_now() + timedelta(days=30)).isoformat() + "Z",
            "provider_metadata": {"max_attempts": 3},
        },
        headers=admin_headers,
    )
    assert profile.status_code == 200, profile.text
    assert profile.json()["provider"] == "MOCK"

    queued = await client.post(
        f"/api/v1/certificate-signing/certificates/{certificate_id}/enqueue",
        headers=admin_headers,
    )
    assert queued.status_code == 201, queued.text
    job_id = queued.json()["id"]
    assert queued.json()["status"] == "QUEUED"

    processed = await client.post(
        f"/api/v1/certificate-signing/jobs/{job_id}/process",
        headers=admin_headers,
    )
    assert processed.status_code == 200, processed.text
    assert processed.json()["status"] == "SIGNED"
    assert processed.json()["attempt_count"] == 1
    assert processed.json()["result_metadata"]["is_mock"] is True
    assert processed.json()["result_metadata"]["chain_trusted"] is False

    document = await client.get(
        f"/api/v1/certificate-documents/{certificate_id}",
        headers=fixture["student_headers"],
    )
    assert document.status_code == 200, document.text
    assert document.json()["status"] == "SIGNED"
    assert document.json()["signature_provider"] == "MOCK"

    validation = await client.post(
        "/api/v1/certificates/validate",
        json={"validation_code": prepared.json()["validation_code"]},
    )
    assert validation.status_code == 200, validation.text
    assert validation.json()["valid"] is True
    assert validation.json()["document_status"] == "SIGNED"
    assert len(validation.json()["pdf_sha256"]) == 64

    events = await client.get(
        f"/api/v1/certificate-signing/jobs/{job_id}/events",
        headers=admin_headers,
    )
    assert events.status_code == 200
    assert [item["event_type"] for item in events.json()] == [
        "QUEUED",
        "SUBMITTING",
        "SUBMITTED",
        "SIGNED",
    ]


@pytest.mark.asyncio
async def test_profile_rejects_secret_material_and_expired_certificate(client, admin_headers):
    secret_metadata = await client.put(
        "/api/v1/certificate-signing/profile",
        json={
            "provider": "MOCK",
            "enabled": False,
            "signer_display_name": "Signer",
            "provider_metadata": {"private_key": "-----BEGIN PRIVATE KEY-----"},
        },
        headers=admin_headers,
    )
    assert secret_metadata.status_code == 422

    expired = await client.put(
        "/api/v1/certificate-signing/profile",
        json={
            "provider": "MOCK",
            "enabled": True,
            "signer_display_name": "Signer",
            "certificate_not_after": (utc_now() - timedelta(days=1)).isoformat() + "Z",
        },
        headers=admin_headers,
    )
    assert expired.status_code == 409
    assert "expired" in expired.json()["detail"].lower()


def test_external_gateway_requires_trusted_pades_chain_and_expected_fingerprint():
    provider = ExternalPadesGatewayProvider(
        base_url="https://signing.example.test",
        api_token="not-a-real-token",
    )
    original = b"%PDF-1.7\noriginal"
    signed = original + b"\n% signed"
    fingerprint = hashlib.sha256(b"certificate").hexdigest()

    with pytest.raises(SigningProviderError) as untrusted:
        provider.validate_signed_result(
            result=SigningPollResult(
                status="SIGNED",
                signed_pdf_bytes=signed,
                verification={
                    "signature_valid": True,
                    "chain_trusted": False,
                    "standard": "PAdES-B-LT",
                    "certificate_fingerprint_sha256": fingerprint,
                },
            ),
            original_pdf=original,
            expected_fingerprint_sha256=fingerprint,
        )
    assert untrusted.value.code == "certificate_chain_untrusted"

    with pytest.raises(SigningProviderError) as mismatch:
        provider.validate_signed_result(
            result=SigningPollResult(
                status="SIGNED",
                signed_pdf_bytes=signed,
                verification={
                    "signature_valid": True,
                    "chain_trusted": True,
                    "standard": "PAdES-B-LT",
                    "certificate_fingerprint_sha256": fingerprint,
                },
            ),
            original_pdf=original,
            expected_fingerprint_sha256="0" * 64,
        )
    assert mismatch.value.code == "fingerprint_mismatch"

    valid = provider.validate_signed_result(
        result=SigningPollResult(
            status="SIGNED",
            signed_pdf_bytes=signed,
            verification={
                "signature_valid": True,
                "chain_trusted": True,
                "standard": "PAdES-B-LT",
                "certificate_fingerprint_sha256": fingerprint,
            },
        ),
        original_pdf=original,
        expected_fingerprint_sha256=fingerprint,
    )
    assert valid["chain_trusted"] is True


def test_webhook_hmac_is_time_bounded_and_constant_contract():
    secret = "webhook-secret-for-test"
    body = b'{"provider_job_id":"abc","status":"SIGNED"}'
    timestamp = str(int(utc_now().timestamp()))
    signature = hmac.new(
        secret.encode(),
        timestamp.encode("ascii") + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    assert verify_webhook_signature(
        secret=secret,
        body=body,
        timestamp=timestamp,
        signature=signature,
    )
    assert not verify_webhook_signature(
        secret=secret,
        body=body,
        timestamp=str(int(utc_now().timestamp()) - 1000),
        signature=signature,
    )
    assert not verify_webhook_signature(
        secret=secret,
        body=body + b" ",
        timestamp=timestamp,
        signature=signature,
    )
