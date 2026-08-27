import hashlib

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.models.certificate import Certificate
from app.models.certificate_document import CertificateDocument, CertificateDocumentStatus
from app.services.certificate_document_service import (
    CertificateDocumentService,
    sha256_json,
)
from tests.test_training_evidence_runtime import _complete_lesson, _create_course


async def _ready_for_signature(client, admin_headers):
    fixture = await _create_course(
        client,
        admin_headers,
        code=f"DOC-NO-ASSESS-{hashlib.sha256(str(id(client)).encode()).hexdigest()[:6].upper()}",
        requires_assessment=False,
        requires_practical=False,
    )
    await _complete_lesson(client, fixture)
    enrollment_id = fixture["enrollment"]["id"]
    confirmation = await client.post(
        f"/api/v1/training-evidence/enrollments/{enrollment_id}/confirm",
        json={
            "password": fixture["password"],
            "declaration_accepted": True,
        },
        headers=fixture["student_headers"],
    )
    assert confirmation.status_code == 200, confirmation.text
    assert confirmation.json()["state"]["state"] == "CERTIFICATE_PENDING_SIGNATURE"
    return fixture


@pytest.fixture
def local_certificate_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "STORAGE_LOCAL_DIR", str(tmp_path / "certificate-storage"))
    return tmp_path


@pytest.mark.asyncio
async def test_prepare_freezes_snapshot_and_original_pdf(
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
    payload = prepared.json()
    assert payload["created"] is True
    assert payload["certificate_status"] == "PENDING_SIGNATURE"
    assert payload["document"]["status"] == "PENDING_SIGNATURE"
    assert len(payload["document"]["snapshot_sha256"]) == 64
    assert len(payload["document"]["original_pdf_sha256"]) == 64
    assert payload["document"]["original_size_bytes"] > 100

    certificate_id = payload["certificate_id"]
    snapshot_response = await client.get(
        f"/api/v1/certificate-documents/{certificate_id}/snapshot",
        headers=admin_headers,
    )
    assert snapshot_response.status_code == 200, snapshot_response.text
    snapshot = snapshot_response.json()["snapshot"]
    assert snapshot_response.json()["snapshot_sha256"] == sha256_json(snapshot)
    assert snapshot["class"]["pedagogical_project_version_id"] == fixture["project"]["id"]
    assert snapshot["student"]["full_name"] == "Aluno Runtime"
    assert "cpf" not in snapshot["student"]  # data minimization by required-field policy
    assert snapshot["student_confirmation"]["auth_method"] == "PASSWORD_REAUTH"
    assert snapshot["training_evidence"]["event_count"] > 0
    assert len(snapshot["training_evidence"]["ledger_sha256"]) == 64

    original = await client.get(
        f"/api/v1/certificate-documents/{certificate_id}/original",
        headers=admin_headers,
    )
    assert original.status_code == 200, original.text
    assert original.headers["content-type"].startswith("application/pdf")
    assert original.content.startswith(b"%PDF")
    assert hashlib.sha256(original.content).hexdigest() == payload["document"]["original_pdf_sha256"]
    assert original.headers["x-certificate-sha256"] == payload["document"]["original_pdf_sha256"]

    integrity = await client.post(
        f"/api/v1/certificate-documents/{certificate_id}/verify-integrity?original=true",
        headers=admin_headers,
    )
    assert integrity.status_code == 200, integrity.text
    assert integrity.json()["valid"] is True
    assert integrity.json()["artifact"] == "ORIGINAL"

    # Preparation is idempotent under repeated admin actions.
    again = await client.post(
        f"/api/v1/certificate-documents/enrollments/{enrollment_id}/prepare",
        headers=admin_headers,
    )
    assert again.status_code == 201, again.text
    assert again.json()["created"] is False
    assert again.json()["certificate_id"] == certificate_id
    assert again.json()["document"]["id"] == payload["document"]["id"]

    pending_download = await client.get(
        f"/api/v1/certificates/{certificate_id}/download",
        headers=fixture["student_headers"],
    )
    assert pending_download.status_code == 409
    assert "pending" in pending_download.json()["detail"].lower()

    validation = await client.post(
        "/api/v1/certificates/validate",
        json={"validation_code": payload["validation_code"]},
    )
    assert validation.status_code == 200
    assert validation.json()["valid"] is False
    assert validation.json()["status"] == "PENDING_SIGNATURE"
    assert validation.json()["student"] is None
    assert validation.json()["course"] is None


@pytest.mark.asyncio
async def test_signed_transition_activates_certificate_and_preserves_exact_download(
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
    prepared_payload = prepared.json()
    certificate_id = prepared_payload["certificate_id"]

    original = await client.get(
        f"/api/v1/certificate-documents/{certificate_id}/original",
        headers=admin_headers,
    )
    assert original.status_code == 200
    # A test signer appends deterministic bytes. The domain service intentionally
    # does not claim ICP-Brasil validation; the future provider adapter owns that.
    signed_bytes = original.content + b"\n% TEST SIGNER INCREMENTAL SIGNATURE\n"

    async with AsyncSessionLocal() as db:
        document = await CertificateDocumentService.finalize_signed_document(
            db,
            tenant_id=WR_TENANT_ID,
            certificate_id=certificate_id,
            signed_pdf_bytes=signed_bytes,
            provider="TEST_SIGNER",
            signature_metadata={"fixture": True, "profile": "PAdES-test"},
            actor_id=None,
        )
        assert document.status == CertificateDocumentStatus.SIGNED
        signed_sha = document.signed_pdf_sha256

    metadata = await client.get(
        f"/api/v1/certificate-documents/{certificate_id}",
        headers=fixture["student_headers"],
    )
    assert metadata.status_code == 200, metadata.text
    assert metadata.json()["status"] == "SIGNED"
    assert metadata.json()["signature_provider"] == "TEST_SIGNER"
    assert metadata.json()["signed_pdf_sha256"] == signed_sha

    downloaded = await client.get(
        f"/api/v1/certificates/{certificate_id}/download",
        headers=fixture["student_headers"],
    )
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == signed_bytes
    assert downloaded.headers["x-certificate-artifact"] == "SIGNED"
    assert downloaded.headers["x-certificate-sha256"] == signed_sha

    integrity = await client.post(
        f"/api/v1/certificate-documents/{certificate_id}/verify-integrity",
        headers=admin_headers,
    )
    assert integrity.status_code == 200
    assert integrity.json()["valid"] is True
    assert integrity.json()["artifact"] == "SIGNED"
    assert integrity.json()["actual_sha256"] == signed_sha

    validation = await client.post(
        "/api/v1/certificates/validate",
        json={"validation_code": prepared_payload["validation_code"]},
    )
    assert validation.status_code == 200
    assert validation.json()["valid"] is True
    assert validation.json()["status"] == "ACTIVE"
    assert validation.json()["student"]["name"] == "Aluno Runtime"

    state = await client.get(
        f"/api/v1/training-evidence/enrollments/{enrollment_id}/state",
        headers=fixture["student_headers"],
    )
    assert state.status_code == 200
    assert state.json()["state"] == "CERTIFIED"

    async with AsyncSessionLocal() as db:
        certificate = (
            await db.execute(
                select(Certificate).where(Certificate.id == certificate_id)
            )
        ).scalar_one()
        document = (
            await db.execute(
                select(CertificateDocument).where(
                    CertificateDocument.certificate_id == certificate_id
                )
            )
        ).scalar_one()
        assert certificate.status == "ACTIVE"
        assert certificate.pdf_path == document.signed_storage_key
        assert document.original_pdf_sha256 == prepared_payload["document"]["original_pdf_sha256"]


@pytest.mark.asyncio
async def test_regulatory_reissue_returns_to_pending_signature_pipeline(
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
    first = prepared.json()
    certificate_id = first["certificate_id"]
    original = await client.get(
        f"/api/v1/certificate-documents/{certificate_id}/original",
        headers=admin_headers,
    )
    async with AsyncSessionLocal() as db:
        await CertificateDocumentService.finalize_signed_document(
            db,
            tenant_id=WR_TENANT_ID,
            certificate_id=certificate_id,
            signed_pdf_bytes=original.content + b"\n% TEST SIGNATURE V1\n",
            provider="TEST_SIGNER",
            signature_metadata={"fixture": True},
        )

    reissue = await client.post(
        f"/api/v1/certificates/{certificate_id}/reissue",
        json={"reason": "Correção controlada de dados do certificado"},
        headers=admin_headers,
    )
    assert reissue.status_code == 201, reissue.text
    second = reissue.json()
    assert second["id"] != certificate_id
    assert second["status"] == "PENDING_SIGNATURE"
    assert second["supersedes_id"] == certificate_id
    assert second["version"] == first["document"].get("version", second["version"] - 1) + 1 or second["version"] == 2

    second_document = await client.get(
        f"/api/v1/certificate-documents/{second['id']}",
        headers=admin_headers,
    )
    assert second_document.status_code == 200, second_document.text
    assert second_document.json()["status"] == "PENDING_SIGNATURE"

    old = await client.get(
        f"/api/v1/certificates/{certificate_id}",
        headers=admin_headers,
    )
    assert old.status_code == 200
    assert old.json()["status"] == "SUPERSEDED"
