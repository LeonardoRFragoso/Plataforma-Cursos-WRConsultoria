from __future__ import annotations

import base64
import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.core.config import settings


class SigningProviderError(RuntimeError):
    def __init__(self, message: str, *, code: str = "provider_error", retryable: bool = True):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class SigningSubmission:
    provider_job_id: str
    status: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SigningPollResult:
    status: str
    signed_pdf_bytes: bytes | None = None
    verification: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


class CertificateSigningProvider(Protocol):
    async def submit(
        self,
        *,
        original_pdf: bytes,
        original_sha256: str,
        certificate_id: uuid.UUID,
        callback_url: str | None,
    ) -> SigningSubmission: ...

    async def poll(self, provider_job_id: str) -> SigningPollResult: ...

    def validate_signed_result(
        self,
        *,
        result: SigningPollResult,
        original_pdf: bytes,
        expected_fingerprint_sha256: str | None,
    ) -> dict: ...


class MockPadesSigningProvider:
    """Deterministic non-cryptographic signer for tests/demo only."""

    def __init__(self, *, signer_name: str, fingerprint_sha256: str | None = None):
        if settings.ENVIRONMENT.lower() == "production":
            raise SigningProviderError(
                "Mock certificate signing is forbidden in production",
                code="mock_forbidden_in_production",
                retryable=False,
            )
        self.signer_name = signer_name
        self.fingerprint_sha256 = fingerprint_sha256 or hashlib.sha256(
            f"mock:{signer_name}".encode("utf-8")
        ).hexdigest()
        self._documents: dict[str, bytes] = {}

    async def submit(
        self,
        *,
        original_pdf: bytes,
        original_sha256: str,
        certificate_id: uuid.UUID,
        callback_url: str | None,
    ) -> SigningSubmission:
        provider_job_id = f"mock-pades-{certificate_id}-{uuid.uuid4().hex[:12]}"
        marker = (
            "\n% MOCK-PADES-SIGNATURE — SEM VALIDADE ICP-BRASIL\n"
            f"% original_sha256={original_sha256}\n"
            f"% signer={self.signer_name}\n"
            f"% fingerprint={self.fingerprint_sha256}\n"
        ).encode("utf-8")
        self._documents[provider_job_id] = original_pdf + marker
        return SigningSubmission(
            provider_job_id=provider_job_id,
            status="SIGNED",
            metadata={"mode": "mock", "callback_url": callback_url},
        )

    async def poll(self, provider_job_id: str) -> SigningPollResult:
        signed = self._documents.get(provider_job_id)
        if signed is None:
            raise SigningProviderError(
                "Mock signing job not found",
                code="mock_job_not_found",
                retryable=False,
            )
        return SigningPollResult(
            status="SIGNED",
            signed_pdf_bytes=signed,
            verification={
                "signature_valid": True,
                "chain_trusted": False,
                "is_mock": True,
                "certificate_fingerprint_sha256": self.fingerprint_sha256,
                "signer_name": self.signer_name,
                "standard": "PAdES-MOCK",
            },
        )

    def validate_signed_result(
        self,
        *,
        result: SigningPollResult,
        original_pdf: bytes,
        expected_fingerprint_sha256: str | None,
    ) -> dict:
        if not result.signed_pdf_bytes or not result.signed_pdf_bytes.startswith(b"%PDF"):
            raise SigningProviderError("Mock signer returned invalid PDF", code="invalid_pdf", retryable=False)
        if result.signed_pdf_bytes == original_pdf:
            raise SigningProviderError("Mock signed PDF is unchanged", code="unsigned_artifact", retryable=False)
        fingerprint = result.verification.get("certificate_fingerprint_sha256")
        if expected_fingerprint_sha256 and fingerprint != expected_fingerprint_sha256:
            raise SigningProviderError(
                "Signer fingerprint does not match configured profile",
                code="fingerprint_mismatch",
                retryable=False,
            )
        # Explicitly preserve that this is not a trusted ICP-Brasil chain.
        return dict(result.verification)


class ExternalPadesGatewayProvider:
    """Adapter for an external PAdES/HSM gateway.

    The gateway owns private-key/HSM access and ICP-Brasil trust validation.
    The platform sends only the PDF and receives a signed PDF plus verification
    evidence. The gateway contract is intentionally vendor-neutral so a real
    vendor can be connected without changing the certificate domain.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_token: str,
        timeout_seconds: float = 30.0,
    ):
        base_url = base_url.strip().rstrip("/")
        if not base_url.startswith("https://"):
            raise SigningProviderError(
                "External signing gateway must use HTTPS",
                code="insecure_gateway_url",
                retryable=False,
            )
        if not api_token:
            raise SigningProviderError("Signing gateway token is missing", code="missing_api_token", retryable=False)
        self.base_url = base_url
        self.api_token = api_token
        self.timeout_seconds = timeout_seconds

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_token}", "Accept": "application/json"}

    async def submit(
        self,
        *,
        original_pdf: bytes,
        original_sha256: str,
        certificate_id: uuid.UUID,
        callback_url: str | None,
    ) -> SigningSubmission:
        headers = {
            **self._headers,
            "Content-Type": "application/pdf",
            "X-Certificate-Id": str(certificate_id),
            "X-Original-SHA256": original_sha256,
            # Stable across retries/restarts for the same certificate version.
            # A compliant gateway must treat this key idempotently.
            "Idempotency-Key": f"certificate-signature-{certificate_id}",
        }
        if callback_url:
            headers["X-Callback-Url"] = callback_url
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/signatures", headers=headers, content=original_pdf)
        except httpx.HTTPError as exc:
            raise SigningProviderError("Signing gateway is unavailable", code="gateway_unavailable") from exc
        if response.status_code >= 500:
            raise SigningProviderError("Signing gateway server error", code="gateway_server_error")
        if response.status_code >= 400:
            raise SigningProviderError(
                "Signing gateway rejected the request",
                code=f"gateway_http_{response.status_code}",
                retryable=False,
            )
        try:
            payload = response.json()
            provider_job_id = str(payload["job_id"])
            provider_status = str(payload.get("status") or "PENDING").upper()
        except (ValueError, KeyError, TypeError) as exc:
            raise SigningProviderError("Invalid signing gateway response", code="invalid_gateway_response") from exc
        return SigningSubmission(provider_job_id=provider_job_id, status=provider_status, metadata={})

    async def poll(self, provider_job_id: str) -> SigningPollResult:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(
                    f"{self.base_url}/signatures/{provider_job_id}",
                    headers=self._headers,
                )
        except httpx.HTTPError as exc:
            raise SigningProviderError("Signing gateway is unavailable", code="gateway_unavailable") from exc
        if response.status_code == 404:
            raise SigningProviderError("Provider signing job was not found", code="provider_job_not_found", retryable=False)
        if response.status_code >= 500:
            raise SigningProviderError("Signing gateway server error", code="gateway_server_error")
        if response.status_code >= 400:
            raise SigningProviderError(
                "Signing gateway status request failed",
                code=f"gateway_http_{response.status_code}",
                retryable=False,
            )
        try:
            payload = response.json()
            status_value = str(payload.get("status") or "PENDING").upper()
            encoded = payload.get("signed_pdf_base64")
            signed_pdf = base64.b64decode(encoded, validate=True) if encoded else None
            verification = payload.get("verification") or {}
            metadata = payload.get("metadata") or {}
        except (ValueError, TypeError) as exc:
            raise SigningProviderError("Invalid signing gateway status response", code="invalid_gateway_response") from exc
        return SigningPollResult(
            status=status_value,
            signed_pdf_bytes=signed_pdf,
            verification=verification,
            metadata=metadata,
        )

    def validate_signed_result(
        self,
        *,
        result: SigningPollResult,
        original_pdf: bytes,
        expected_fingerprint_sha256: str | None,
    ) -> dict:
        pdf = result.signed_pdf_bytes
        if not pdf or not pdf.startswith(b"%PDF"):
            raise SigningProviderError("Provider returned no valid signed PDF", code="invalid_signed_pdf", retryable=False)
        if pdf == original_pdf:
            raise SigningProviderError("Provider returned unchanged PDF bytes", code="unsigned_artifact", retryable=False)
        verification = result.verification or {}
        if verification.get("signature_valid") is not True:
            raise SigningProviderError("PAdES signature verification failed", code="signature_invalid", retryable=False)
        if verification.get("chain_trusted") is not True:
            raise SigningProviderError("ICP-Brasil certificate chain is not trusted", code="certificate_chain_untrusted", retryable=False)
        fingerprint = str(verification.get("certificate_fingerprint_sha256") or "").lower()
        if expected_fingerprint_sha256 and fingerprint != expected_fingerprint_sha256.lower():
            raise SigningProviderError(
                "Signer certificate fingerprint mismatch",
                code="fingerprint_mismatch",
                retryable=False,
            )
        if str(verification.get("standard") or "").upper().startswith("PADES") is False:
            raise SigningProviderError("Signing result is not PAdES", code="not_pades", retryable=False)
        return dict(verification)
