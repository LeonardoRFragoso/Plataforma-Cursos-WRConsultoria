from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.utils import utc_now
from app.models.certificate import Certificate
from app.models.certificate_document import CertificateDocument, CertificateDocumentStatus
from app.models.certificate_signing import (
    CertificateSigningEvent,
    CertificateSigningJob,
    CertificateSigningProfile,
    SigningJobStatus,
)
from app.models.tenant import Tenant
from app.services.certificate_artifact_storage import load_certificate_pdf
from app.services.certificate_document_service import CertificateDocumentService, sha256_bytes
from app.services.certificate_signing_provider import (
    CertificateSigningProvider,
    ExternalPadesGatewayProvider,
    MockPadesSigningProvider,
    SigningProviderError,
)
from app.services.tenant_secret_service import (
    CERTIFICATE_SIGNING_API_TOKEN_KEY,
    CERTIFICATE_SIGNING_WEBHOOK_SECRET_KEY,
    get_tenant_secret,
)


@dataclass(frozen=True)
class SigningProcessResult:
    job_id: uuid.UUID
    status: str
    changed: bool
    detail: str | None = None


def _sanitized_error(exc: Exception) -> str:
    text = str(exc).strip() or type(exc).__name__
    return text[:500]


def _profile_snapshot(profile: CertificateSigningProfile) -> dict:
    return {
        "profile_id": str(profile.id),
        "provider": profile.provider.strip().upper(),
        "signer_display_name": profile.signer_display_name,
        "signer_identifier": profile.signer_identifier,
        "certificate_fingerprint_sha256": profile.certificate_fingerprint_sha256,
        "certificate_serial": profile.certificate_serial,
        "certificate_subject": profile.certificate_subject,
        "certificate_issuer": profile.certificate_issuer,
        "certificate_not_before": profile.certificate_not_before.isoformat() if profile.certificate_not_before else None,
        "certificate_not_after": profile.certificate_not_after.isoformat() if profile.certificate_not_after else None,
        "key_reference": profile.key_reference,
        # Schema validation guarantees this contains no credentials/private-key material.
        "provider_metadata": dict(profile.provider_metadata or {}),
    }


def validate_signing_profile(profile: CertificateSigningProfile) -> None:
    if not profile.enabled:
        raise ValueError("Certificate signing profile is disabled")
    provider = profile.provider.strip().upper()
    if provider == "DISABLED":
        raise ValueError("Certificate signing provider is disabled")
    now = utc_now()
    if profile.certificate_not_before and now < profile.certificate_not_before:
        raise ValueError("Signing certificate is not valid yet")
    if profile.certificate_not_after and now >= profile.certificate_not_after:
        raise ValueError("Signing certificate has expired")
    if profile.certificate_fingerprint_sha256:
        value = profile.certificate_fingerprint_sha256.lower()
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("Signing certificate fingerprint must be a SHA-256 hex digest")
    if provider == "MOCK" and settings.ENVIRONMENT.lower() == "production":
        raise ValueError("Mock signing cannot be enabled in production")
    if provider == "EXTERNAL_PADES_GATEWAY":
        metadata = profile.provider_metadata or {}
        base_url = str(metadata.get("base_url") or "").strip()
        if not base_url.startswith("https://"):
            raise ValueError("External PAdES gateway requires an HTTPS base_url")


async def _event(
    db: AsyncSession,
    *,
    job: CertificateSigningJob,
    event_type: str,
    actor_id: uuid.UUID | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        CertificateSigningEvent(
            tenant_id=job.tenant_id,
            job_id=job.id,
            event_type=event_type,
            actor_id=actor_id,
            details=details or {},
        )
    )


async def _provider_for_snapshot(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    snapshot: dict,
) -> CertificateSigningProvider:
    provider = str(snapshot.get("provider") or "").strip().upper()
    signer_name = str(snapshot.get("signer_display_name") or "").strip()
    fingerprint = snapshot.get("certificate_fingerprint_sha256")
    if provider == "MOCK":
        if settings.ENVIRONMENT.lower() == "production":
            raise SigningProviderError(
                "Mock certificate signing is forbidden in production",
                code="mock_forbidden_in_production",
                retryable=False,
            )
        return MockPadesSigningProvider(
            signer_name=signer_name,
            fingerprint_sha256=fingerprint,
        )
    if provider == "EXTERNAL_PADES_GATEWAY":
        token = await get_tenant_secret(db, tenant_id, CERTIFICATE_SIGNING_API_TOKEN_KEY)
        if not token:
            raise SigningProviderError(
                "Signing gateway API token is not configured",
                code="missing_api_token",
                retryable=False,
            )
        metadata = snapshot.get("provider_metadata") or {}
        return ExternalPadesGatewayProvider(
            base_url=str(metadata.get("base_url") or ""),
            api_token=token,
            timeout_seconds=float(metadata.get("timeout_seconds") or 30),
        )
    raise SigningProviderError(
        f"Unsupported certificate signing provider: {provider}",
        code="unsupported_provider",
        retryable=False,
    )


async def signing_status(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    profile = (
        await db.execute(
            select(CertificateSigningProfile).where(CertificateSigningProfile.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    api_token = await get_tenant_secret(db, tenant_id, CERTIFICATE_SIGNING_API_TOKEN_KEY)
    webhook_secret = await get_tenant_secret(db, tenant_id, CERTIFICATE_SIGNING_WEBHOOK_SECRET_KEY)
    now = utc_now()
    return {
        "configured": profile is not None,
        "enabled": bool(profile and profile.enabled),
        "provider": profile.provider if profile else "DISABLED",
        "certificate_expires_at": profile.certificate_not_after if profile else None,
        "certificate_expired": bool(profile and profile.certificate_not_after and profile.certificate_not_after <= now),
        "api_token_configured": bool(api_token),
        "webhook_secret_configured": bool(webhook_secret),
        "mock_allowed": settings.ENVIRONMENT.lower() != "production",
    }


async def enqueue_signing_job(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    certificate_id: uuid.UUID,
    actor_id: uuid.UUID | None,
) -> CertificateSigningJob:
    row = (
        await db.execute(
            select(CertificateDocument, Certificate)
            .join(Certificate, CertificateDocument.certificate_id == Certificate.id)
            .where(
                CertificateDocument.tenant_id == tenant_id,
                CertificateDocument.certificate_id == certificate_id,
                Certificate.tenant_id == tenant_id,
            )
            .with_for_update(of=CertificateDocument)
        )
    ).first()
    if not row:
        raise LookupError("Certificate document not found")
    document, certificate = row
    if document.status == CertificateDocumentStatus.SIGNED or certificate.status == "ACTIVE":
        raise ValueError("Certificate document is already signed")
    if document.status != CertificateDocumentStatus.PENDING_SIGNATURE or certificate.status != "PENDING_SIGNATURE":
        raise ValueError("Certificate is not pending signature")

    profile = (
        await db.execute(
            select(CertificateSigningProfile).where(CertificateSigningProfile.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not profile:
        raise ValueError("Certificate signing profile is not configured")
    validate_signing_profile(profile)
    snapshot = _profile_snapshot(profile)

    existing = (
        await db.execute(
            select(CertificateSigningJob).where(
                CertificateSigningJob.tenant_id == tenant_id,
                CertificateSigningJob.document_id == document.id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        # A terminal job that never reached a provider can be safely reset to
        # the tenant's current profile. If a provider_job_id exists, preserve
        # that identity to avoid two external signatures for one document.
        if (
            existing.status in {SigningJobStatus.FAILED, SigningJobStatus.CANCELLED}
            and not existing.provider_job_id
        ):
            existing.profile_id = profile.id
            existing.provider = snapshot["provider"]
            existing.profile_snapshot = snapshot
            existing.status = SigningJobStatus.QUEUED
            existing.attempt_count = 0
            existing.max_attempts = min(max(int((profile.provider_metadata or {}).get("max_attempts") or 5), 1), 20)
            existing.next_attempt_at = utc_now()
            existing.last_attempt_at = None
            existing.last_error_code = None
            existing.last_error_message = None
            await _event(db, job=existing, event_type="REQUEUED_WITH_CURRENT_PROFILE", actor_id=actor_id)
            await db.commit()
            await db.refresh(existing)
        return existing

    max_attempts = int((profile.provider_metadata or {}).get("max_attempts") or 5)
    max_attempts = min(max(max_attempts, 1), 20)
    job = CertificateSigningJob(
        tenant_id=tenant_id,
        document_id=document.id,
        certificate_id=certificate.id,
        profile_id=profile.id,
        provider=snapshot["provider"],
        profile_snapshot=snapshot,
        status=SigningJobStatus.QUEUED,
        attempt_count=0,
        max_attempts=max_attempts,
        next_attempt_at=utc_now(),
        created_by=actor_id,
    )
    db.add(job)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        existing = (
            await db.execute(
                select(CertificateSigningJob).where(
                    CertificateSigningJob.tenant_id == tenant_id,
                    CertificateSigningJob.document_id == document.id,
                )
            )
        ).scalar_one_or_none()
        if existing:
            return existing
        raise
    await _event(db, job=job, event_type="QUEUED", actor_id=actor_id)
    await db.commit()
    await db.refresh(job)
    return job


async def _mark_failure(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    exc: Exception,
) -> SigningProcessResult:
    job = (
        await db.execute(
            select(CertificateSigningJob)
            .where(CertificateSigningJob.id == job_id, CertificateSigningJob.tenant_id == tenant_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not job:
        return SigningProcessResult(job_id=job_id, status="NOT_FOUND", changed=False)
    retryable = getattr(exc, "retryable", True)
    code = getattr(exc, "code", type(exc).__name__)
    job.last_error_code = str(code)[:128]
    job.last_error_message = _sanitized_error(exc)
    if (not retryable) or job.attempt_count >= job.max_attempts:
        job.status = SigningJobStatus.FAILED
        job.next_attempt_at = None
        event_type = "FAILED"
    else:
        delay_seconds = min(3600, 30 * (2 ** max(job.attempt_count - 1, 0)))
        job.status = SigningJobStatus.RETRY_SCHEDULED
        job.next_attempt_at = utc_now() + timedelta(seconds=delay_seconds)
        event_type = "RETRY_SCHEDULED"
    await _event(
        db,
        job=job,
        event_type=event_type,
        details={"code": job.last_error_code, "retryable": bool(retryable)},
    )
    await db.commit()
    return SigningProcessResult(job_id=job.id, status=job.status, changed=True, detail=job.last_error_code)


async def process_signing_job(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
) -> SigningProcessResult:
    now = utc_now()
    row = (
        await db.execute(
            select(CertificateSigningJob, CertificateSigningProfile, CertificateDocument, Certificate, Tenant)
            .join(CertificateSigningProfile, CertificateSigningJob.profile_id == CertificateSigningProfile.id)
            .join(CertificateDocument, CertificateSigningJob.document_id == CertificateDocument.id)
            .join(Certificate, CertificateSigningJob.certificate_id == Certificate.id)
            .join(Tenant, CertificateSigningJob.tenant_id == Tenant.id)
            .where(
                CertificateSigningJob.id == job_id,
                CertificateSigningJob.tenant_id == tenant_id,
                CertificateSigningProfile.tenant_id == tenant_id,
                CertificateDocument.tenant_id == tenant_id,
                Certificate.tenant_id == tenant_id,
                Tenant.id == tenant_id,
            )
            .with_for_update(of=CertificateSigningJob)
        )
    ).first()
    if not row:
        return SigningProcessResult(job_id=job_id, status="NOT_FOUND", changed=False)
    job, profile, document, certificate, tenant = row

    if document.status == CertificateDocumentStatus.SIGNED and certificate.status == "ACTIVE":
        if job.status != SigningJobStatus.SIGNED:
            job.status = SigningJobStatus.SIGNED
            job.completed_at = document.signed_at or now
            job.next_attempt_at = None
            await _event(db, job=job, event_type="RECONCILED_SIGNED")
            await db.commit()
            return SigningProcessResult(job_id=job.id, status=job.status, changed=True)
        return SigningProcessResult(job_id=job.id, status=job.status, changed=False)
    if job.status in SigningJobStatus.TERMINAL:
        return SigningProcessResult(job_id=job.id, status=job.status, changed=False)
    if job.next_attempt_at and job.next_attempt_at > now:
        return SigningProcessResult(job_id=job.id, status=job.status, changed=False, detail="not_due")
    if job.status == SigningJobStatus.SUBMITTING and job.last_attempt_at:
        if job.last_attempt_at + timedelta(minutes=5) > now:
            return SigningProcessResult(job_id=job.id, status=job.status, changed=False, detail="submission_in_progress")

    try:
        original_pdf = await load_certificate_pdf(document.original_storage_key)
        if sha256_bytes(original_pdf) != document.original_pdf_sha256:
            raise SigningProviderError(
                "Original certificate artifact failed SHA-256 verification",
                code="original_integrity_failed",
                retryable=False,
            )
        provider_job_id = job.provider_job_id
        if not provider_job_id:
            # Before submission, the tenant must still explicitly have signing
            # enabled and a currently valid certificate configuration.
            validate_signing_profile(profile)
        provider = await _provider_for_snapshot(
            db,
            tenant_id=tenant_id,
            snapshot=job.profile_snapshot or {},
        )

        if not provider_job_id:
            job.attempt_count += 1
            job.last_attempt_at = now
            job.status = SigningJobStatus.SUBMITTING
            job.last_error_code = None
            job.last_error_message = None
            await _event(db, job=job, event_type="SUBMITTING", details={"attempt": job.attempt_count})
            await db.commit()

            callback_url = None
            if job.provider == "EXTERNAL_PADES_GATEWAY":
                callback_url = (
                    f"{settings.API_BASE_URL.rstrip('/')}/api/v1/integrations/"
                    f"certificate-signing/webhook/{tenant.slug}/{job.provider.lower()}"
                )
            submission = await provider.submit(
                original_pdf=original_pdf,
                original_sha256=document.original_pdf_sha256,
                certificate_id=certificate.id,
                callback_url=callback_url,
            )

            job = (
                await db.execute(
                    select(CertificateSigningJob)
                    .where(CertificateSigningJob.id == job_id, CertificateSigningJob.tenant_id == tenant_id)
                    .with_for_update()
                )
            ).scalar_one()
            job.provider_job_id = submission.provider_job_id
            job.submitted_at = utc_now()
            provider_job_id = submission.provider_job_id
            await _event(
                db,
                job=job,
                event_type="SUBMITTED",
                details={"provider_status": submission.status},
            )
            await db.commit()

        result = await provider.poll(provider_job_id)
        provider_status = result.status.upper()
        if provider_status in {"PENDING", "QUEUED", "PROCESSING", "WAITING", "IN_PROGRESS"}:
            job = (
                await db.execute(
                    select(CertificateSigningJob)
                    .where(CertificateSigningJob.id == job_id, CertificateSigningJob.tenant_id == tenant_id)
                    .with_for_update()
                )
            ).scalar_one()
            job.status = SigningJobStatus.WAITING_PROVIDER
            job.next_attempt_at = utc_now() + timedelta(seconds=60)
            await _event(db, job=job, event_type="WAITING_PROVIDER", details={"provider_status": provider_status})
            await db.commit()
            return SigningProcessResult(job_id=job.id, status=job.status, changed=True)
        if provider_status in {"FAILED", "REJECTED", "CANCELLED", "CANCELED"}:
            raise SigningProviderError(
                "Signing provider reported a terminal failure",
                code=f"provider_{provider_status.lower()}",
                retryable=False,
            )
        if provider_status != "SIGNED":
            raise SigningProviderError(
                f"Unsupported signing provider status: {provider_status}",
                code="unknown_provider_status",
            )

        frozen_fingerprint = (job.profile_snapshot or {}).get("certificate_fingerprint_sha256")
        verification = provider.validate_signed_result(
            result=result,
            original_pdf=original_pdf,
            expected_fingerprint_sha256=frozen_fingerprint,
        )
        signature_metadata = {
            "profile": dict(job.profile_snapshot or {}),
            "verification": verification,
            "provider_result": result.metadata,
        }
        document = await CertificateDocumentService.finalize_signed_document(
            db,
            tenant_id=tenant_id,
            certificate_id=certificate.id,
            signed_pdf_bytes=result.signed_pdf_bytes or b"",
            provider=job.provider,
            signature_metadata=signature_metadata,
            actor_id=None,
        )

        job = (
            await db.execute(
                select(CertificateSigningJob)
                .where(CertificateSigningJob.id == job_id, CertificateSigningJob.tenant_id == tenant_id)
                .with_for_update()
            )
        ).scalar_one()
        job.status = SigningJobStatus.SIGNED
        job.completed_at = document.signed_at or utc_now()
        job.next_attempt_at = None
        job.last_error_code = None
        job.last_error_message = None
        job.result_metadata = {
            "signed_pdf_sha256": document.signed_pdf_sha256,
            "signature_provider": document.signature_provider,
            "certificate_fingerprint_sha256": verification.get("certificate_fingerprint_sha256"),
            "chain_trusted": verification.get("chain_trusted"),
            "is_mock": verification.get("is_mock", False),
        }
        await _event(db, job=job, event_type="SIGNED", details=job.result_metadata)
        await db.commit()
        return SigningProcessResult(job_id=job.id, status=job.status, changed=True)
    except Exception as exc:
        await db.rollback()
        return await _mark_failure(db, tenant_id=tenant_id, job_id=job_id, exc=exc)


async def due_signing_job_ids(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    limit: int = 50,
) -> list[uuid.UUID]:
    now = utc_now()
    stale_submitting = now - timedelta(minutes=5)
    rows = (
        await db.execute(
            select(CertificateSigningJob.id)
            .where(
                CertificateSigningJob.tenant_id == tenant_id,
                or_(
                    CertificateSigningJob.status.in_(
                        [SigningJobStatus.QUEUED, SigningJobStatus.WAITING_PROVIDER, SigningJobStatus.RETRY_SCHEDULED]
                    ),
                    (
                        (CertificateSigningJob.status == SigningJobStatus.SUBMITTING)
                        & (CertificateSigningJob.last_attempt_at <= stale_submitting)
                    ),
                ),
                or_(
                    CertificateSigningJob.next_attempt_at.is_(None),
                    CertificateSigningJob.next_attempt_at <= now,
                ),
            )
            .order_by(CertificateSigningJob.next_attempt_at.asc().nullsfirst(), CertificateSigningJob.created_at.asc())
            .limit(max(1, min(limit, 500)))
        )
    ).scalars().all()
    return list(rows)


async def retry_signing_job(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> CertificateSigningJob:
    job = (
        await db.execute(
            select(CertificateSigningJob)
            .where(CertificateSigningJob.id == job_id, CertificateSigningJob.tenant_id == tenant_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not job:
        raise LookupError("Signing job not found")
    if job.status == SigningJobStatus.SIGNED:
        return job
    if job.status == SigningJobStatus.CANCELLED:
        raise ValueError("Cancelled signing job cannot be retried")
    job.status = SigningJobStatus.RETRY_SCHEDULED
    job.next_attempt_at = utc_now()
    job.last_error_code = None
    job.last_error_message = None
    # A provider_job_id is intentionally preserved. If the provider already
    # accepted the job, retry polls it instead of submitting a duplicate.
    await _event(db, job=job, event_type="MANUAL_RETRY", actor_id=actor_id)
    await db.commit()
    await db.refresh(job)
    return job


async def cancel_signing_job(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> CertificateSigningJob:
    job = (
        await db.execute(
            select(CertificateSigningJob)
            .where(CertificateSigningJob.id == job_id, CertificateSigningJob.tenant_id == tenant_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not job:
        raise LookupError("Signing job not found")
    if job.status == SigningJobStatus.SIGNED:
        raise ValueError("Signed job cannot be cancelled")
    job.status = SigningJobStatus.CANCELLED
    job.next_attempt_at = None
    await _event(db, job=job, event_type="CANCELLED", actor_id=actor_id)
    await db.commit()
    await db.refresh(job)
    return job


def verify_webhook_signature(*, secret: str, body: bytes, timestamp: str, signature: str, max_age_seconds: int = 300) -> bool:
    try:
        timestamp_int = int(timestamp)
    except (TypeError, ValueError):
        return False
    now_ts = int(utc_now().timestamp())
    if abs(now_ts - timestamp_int) > max_age_seconds:
        return False
    payload = timestamp.encode("ascii") + b"." + body
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.lower())
