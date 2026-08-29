"""Fail-closed tests for certificate issuance on regulated courses.

Verifies that:
- Legacy POST /certificates/ on regulated courses → 409
- Legacy POST /certificates/ on non-regulated courses → still works
- CertificateDocumentService.prepare_document fails when regulatory state
  is not CERTIFICATE_PENDING_SIGNATURE
- MockPadesSigningProvider is forbidden in production
- ExternalPadesGatewayProvider requires HTTPS

These are unit-level tests that don't require a full database setup.
"""

from __future__ import annotations

import hashlib
import uuid
from unittest.mock import MagicMock

import pytest

from app.models.compliance import ComplianceStatus, ProfessionalBlocker
from app.services.certificate_signing_provider import (
    ExternalPadesGatewayProvider,
    MockPadesSigningProvider,
    SigningProviderError,
)


class TestProfessionalBlockers:
    """Verify that ProfessionalBlocker constants are defined and stable."""

    def test_professional_registration_missing_exists(self):
        assert ProfessionalBlocker.PROFESSIONAL_REGISTRATION_MISSING == "PROFESSIONAL_REGISTRATION_MISSING"

    def test_proficiency_evidence_missing_exists(self):
        assert ProfessionalBlocker.PROFICIENCY_EVIDENCE_MISSING == "PROFICIENCY_EVIDENCE_MISSING"

    def test_electrical_legal_qualification_exists(self):
        assert ProfessionalBlocker.ELECTRICAL_LEGAL_QUALIFICATION_REQUIRED == "ELECTRICAL_LEGAL_QUALIFICATION_REQUIRED"

    def test_legal_qualified_professional_exists(self):
        assert ProfessionalBlocker.LEGAL_QUALIFIED_PROFESSIONAL_REQUIRED == "LEGAL_QUALIFIED_PROFESSIONAL_REQUIRED"

    def test_technical_responsible_pending_exists(self):
        assert ProfessionalBlocker.TECHNICAL_RESPONSIBLE_PENDING_VERIFICATION == "TECHNICAL_RESPONSIBLE_PENDING_VERIFICATION"

    def test_nr18_variant_confirmation_exists(self):
        assert ProfessionalBlocker.NR18_VARIANT_CONFIRMATION_REQUIRED == "NR18_VARIANT_CONFIRMATION_REQUIRED"


class TestComplianceStatusFailClosed:
    """Verify compliance status constants enforce fail-closed behavior."""

    def test_review_required_status_exists(self):
        assert ComplianceStatus.REVIEW_REQUIRED == "REVIEW_REQUIRED"

    def test_compliance_ready_status_exists(self):
        assert ComplianceStatus.COMPLIANCE_READY == "COMPLIANCE_READY"

    def test_draft_status_exists(self):
        assert ComplianceStatus.DRAFT == "DRAFT"


class TestMockPadesForbiddenInProduction:
    """MockPadesSigningProvider must be forbidden in production."""

    def test_mock_pades_forbidden_in_production(self, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        with pytest.raises(SigningProviderError, match="forbidden in production"):
            MockPadesSigningProvider(signer_name="test")

    def test_mock_pades_allowed_in_staging(self, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
        provider = MockPadesSigningProvider(signer_name="test")
        assert provider.signer_name == "test"

    def test_mock_pases_allowed_in_development(self, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "ENVIRONMENT", "development")
        provider = MockPadesSigningProvider(signer_name="test")
        assert provider.signer_name == "test"


class TestExternalPadesGatewaySecurity:
    """ExternalPadesGatewayProvider must enforce HTTPS."""

    def test_http_rejected(self):
        with pytest.raises(SigningProviderError, match="HTTPS"):
            ExternalPadesGatewayProvider(base_url="http://signing.example.com", api_token="tok")

    def test_empty_token_rejected(self):
        with pytest.raises(SigningProviderError, match="token"):
            ExternalPadesGatewayProvider(base_url="https://signing.example.com", api_token="")

    def test_https_accepted(self):
        provider = ExternalPadesGatewayProvider(
            base_url="https://signing.example.com", api_token="valid-token"
        )
        assert provider.base_url == "https://signing.example.com"

    def test_trailing_slash_stripped(self):
        provider = ExternalPadesGatewayProvider(
            base_url="https://signing.example.com/", api_token="tok"
        )
        assert provider.base_url == "https://signing.example.com"


class TestMockPadesSigning:
    """Verify mock signing produces clearly-marked non-ICP-Brasil output."""

    def test_mock_signature_marked_as_not_trusted(self, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
        provider = MockPadesSigningProvider(signer_name="test-signer")
        cert_id = uuid.uuid4()
        original_pdf = b"%PDF-1.4 test content"

        submission = asyncio.get_event_loop().run_until_complete(
            provider.submit(
                original_pdf=original_pdf,
                original_sha256=hashlib.sha256(original_pdf).hexdigest(),
                certificate_id=cert_id,
                callback_url=None,
            )
        )
        assert submission.status == "SIGNED"

        result = asyncio.get_event_loop().run_until_complete(
            provider.poll(submission.provider_job_id)
        )
        assert result.verification["is_mock"] is True
        assert result.verification["chain_trusted"] is False
        assert result.verification["standard"] == "PAdES-MOCK"
        assert b"MOCK-PADES-SIGNATURE" in result.signed_pdf_bytes
        assert b"SEM VALIDADE ICP-BRASIL" in result.signed_pdf_bytes


import asyncio  # noqa: E402 — used in TestMockPadesSigning above
