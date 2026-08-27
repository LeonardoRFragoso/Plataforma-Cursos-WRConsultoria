from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, get_db_privileged
from app.core.security import get_current_admin, get_current_tenant_id
from app.core.utils import utc_now
from app.models.certificate_signing import (
    CertificateSigningEvent,
    CertificateSigningJob,
    CertificateSigningProfile,
    SigningJobStatus,
)
from app.models.tenant import Tenant
from app.schemas.certificate_signing import (
    CertificateSigningEventResponse,
    CertificateSigningJobResponse,
    CertificateSigningProfileResponse,
    CertificateSigningProfileUpsert,
    CertificateSigningWebhookPayload,
    SigningQueueSummary,
)
from app.services.certificate_signing_service import (
    cancel_signing_job,
    enqueue_signing_job,
    process_signing_job,
    retry_signing_job,
    signing_status,
    validate_signing_profile,
    verify_webhook_signature,
)
from app.services.tenant_secret_service import (
    CERTIFICATE_SIGNING_API_TOKEN_KEY,
    CERTIFICATE_SIGNING_WEBHOOK_SECRET_KEY,
    get_tenant_secret,
)

router = APIRouter()
webhook_router = APIRouter()


@router.get("/status")
async def get_signing_status(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    return await signing_status(db, get_current_tenant_id())


@router.get("/profile", response_model=CertificateSigningProfileResponse | None)
async def get_signing_profile(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    return (
        await db.execute(
            select(CertificateSigningProfile).where(CertificateSigningProfile.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()


@router.put("/profile", response_model=CertificateSigningProfileResponse)
async def upsert_signing_profile(
    payload: CertificateSigningProfileUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    actor_id = UUID(current_user["user_id"])
    profile = (
        await db.execute(
            select(CertificateSigningProfile)
            .where(CertificateSigningProfile.tenant_id == tenant_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    values = payload.model_dump()
    if profile is None:
        profile = CertificateSigningProfile(
            tenant_id=tenant_id,
            created_by=actor_id,
            updated_by=actor_id,
            **values,
        )
        db.add(profile)
    else:
        for key, value in values.items():
            setattr(profile, key, value)
        profile.updated_by = actor_id

    if profile.enabled:
        try:
            validate_signing_profile(profile)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if profile.provider == "EXTERNAL_PADES_GATEWAY":
            api_token = await get_tenant_secret(db, tenant_id, CERTIFICATE_SIGNING_API_TOKEN_KEY)
            webhook_secret = await get_tenant_secret(db, tenant_id, CERTIFICATE_SIGNING_WEBHOOK_SECRET_KEY)
            if not api_token or not webhook_secret:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "External signing requires encrypted tenant secrets "
                        "certificate_signing_api_token and certificate_signing_webhook_secret"
                    ),
                )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Signing profile already exists") from exc
    await db.refresh(profile)
    return profile


@router.post(
    "/certificates/{certificate_id}/enqueue",
    response_model=CertificateSigningJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def enqueue_certificate_signature(
    certificate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        return await enqueue_signing_job(
            db,
            tenant_id=get_current_tenant_id(),
            certificate_id=certificate_id,
            actor_id=UUID(current_user["user_id"]),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/jobs", response_model=list[CertificateSigningJobResponse])
async def list_signing_jobs(
    job_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(CertificateSigningJob).where(CertificateSigningJob.tenant_id == tenant_id)
    if job_status:
        stmt = stmt.where(CertificateSigningJob.status == job_status.strip().upper())
    result = await db.execute(stmt.order_by(CertificateSigningJob.created_at.desc()).limit(limit))
    return result.scalars().all()


@router.get("/jobs/{job_id}", response_model=CertificateSigningJobResponse)
async def get_signing_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    job = (
        await db.execute(
            select(CertificateSigningJob).where(
                CertificateSigningJob.id == job_id,
                CertificateSigningJob.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Signing job not found")
    return job


@router.get("/jobs/{job_id}/events", response_model=list[CertificateSigningEventResponse])
async def get_signing_job_events(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    job = (
        await db.execute(
            select(CertificateSigningJob.id).where(
                CertificateSigningJob.id == job_id,
                CertificateSigningJob.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Signing job not found")
    events = (
        await db.execute(
            select(CertificateSigningEvent)
            .where(
                CertificateSigningEvent.tenant_id == tenant_id,
                CertificateSigningEvent.job_id == job_id,
            )
            .order_by(CertificateSigningEvent.created_at.asc())
        )
    ).scalars().all()
    return events


@router.post("/jobs/{job_id}/process", response_model=CertificateSigningJobResponse)
async def process_signing_job_now(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    result = await process_signing_job(db, tenant_id=tenant_id, job_id=job_id)
    if result.status == "NOT_FOUND":
        raise HTTPException(status_code=404, detail="Signing job not found")
    job = (
        await db.execute(
            select(CertificateSigningJob).where(
                CertificateSigningJob.id == job_id,
                CertificateSigningJob.tenant_id == tenant_id,
            )
        )
    ).scalar_one()
    return job


@router.post("/jobs/{job_id}/retry", response_model=CertificateSigningJobResponse)
async def retry_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        return await retry_signing_job(
            db,
            tenant_id=get_current_tenant_id(),
            job_id=job_id,
            actor_id=UUID(current_user["user_id"]),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/cancel", response_model=CertificateSigningJobResponse)
async def cancel_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        return await cancel_signing_job(
            db,
            tenant_id=get_current_tenant_id(),
            job_id=job_id,
            actor_id=UUID(current_user["user_id"]),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/queue/summary", response_model=SigningQueueSummary)
async def signing_queue_summary(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    grouped = dict(
        (
            await db.execute(
                select(CertificateSigningJob.status, func.count(CertificateSigningJob.id))
                .where(CertificateSigningJob.tenant_id == tenant_id)
                .group_by(CertificateSigningJob.status)
            )
        ).all()
    )
    expires_before = utc_now() + timedelta(days=30)
    expiring = int(
        await db.scalar(
            select(func.count(CertificateSigningProfile.id)).where(
                CertificateSigningProfile.tenant_id == tenant_id,
                CertificateSigningProfile.enabled.is_(True),
                CertificateSigningProfile.certificate_not_after.is_not(None),
                CertificateSigningProfile.certificate_not_after <= expires_before,
            )
        )
        or 0
    )
    return SigningQueueSummary(
        queued=int(grouped.get(SigningJobStatus.QUEUED, 0)),
        waiting_provider=int(grouped.get(SigningJobStatus.WAITING_PROVIDER, 0)),
        retry_scheduled=int(grouped.get(SigningJobStatus.RETRY_SCHEDULED, 0)),
        failed=int(grouped.get(SigningJobStatus.FAILED, 0)),
        signed=int(grouped.get(SigningJobStatus.SIGNED, 0)),
        expiring_profiles=expiring,
    )


@webhook_router.post("/webhook/{tenant_slug}/{provider}")
async def signing_provider_webhook(
    tenant_slug: str,
    provider: str,
    request: Request,
    x_signature_timestamp: str | None = Header(default=None, alias="X-Signature-Timestamp"),
    x_signature_hmac: str | None = Header(default=None, alias="X-Signature-Hmac"),
    db: AsyncSession = Depends(get_db_privileged),
):
    body = await request.body()
    tenant = (
        await db.execute(select(Tenant).where(Tenant.slug == tenant_slug))
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    secret = await get_tenant_secret(db, tenant.id, CERTIFICATE_SIGNING_WEBHOOK_SECRET_KEY)
    if not secret or not x_signature_timestamp or not x_signature_hmac:
        raise HTTPException(status_code=401, detail="Invalid webhook authentication")
    if not verify_webhook_signature(
        secret=secret,
        body=body,
        timestamp=x_signature_timestamp,
        signature=x_signature_hmac,
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook authentication")
    try:
        payload = CertificateSigningWebhookPayload.model_validate_json(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook payload") from exc

    provider_name = provider.strip().upper()
    job = (
        await db.execute(
            select(CertificateSigningJob)
            .where(
                CertificateSigningJob.tenant_id == tenant.id,
                CertificateSigningJob.provider == provider_name,
                CertificateSigningJob.provider_job_id == payload.provider_job_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not job:
        # Do not reveal whether a provider job belongs to another tenant.
        return {"status": "accepted", "matched": False}
    if job.status in SigningJobStatus.TERMINAL:
        return {"status": "accepted", "matched": True, "terminal": True}

    job.next_attempt_at = utc_now()
    db.add(
        CertificateSigningEvent(
            tenant_id=tenant.id,
            job_id=job.id,
            event_type="PROVIDER_CALLBACK",
            details={
                "provider_status": payload.status.strip().upper(),
                "event_id": payload.event_id,
            },
        )
    )
    await db.commit()
    # Callback never accepts signed bytes and never marks the document signed.
    # It only wakes the trusted polling/verification worker.
    return {"status": "accepted", "matched": True}
