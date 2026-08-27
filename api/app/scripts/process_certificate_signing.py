"""Process due certificate-signing jobs.

Safe to invoke from a scheduler/cron. It never enables signing by itself:
only tenants with an explicitly enabled signing profile are processed, and
MOCK is rejected in production by the domain service.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select, text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.models.tenant import Tenant, TenantStatus
from app.services.certificate_signing_service import due_signing_job_ids, process_signing_job

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("certificate-signing-worker")


async def _active_tenants():
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await db.execute(text(f"SET LOCAL app.current_tenant = '{WR_TENANT_ID}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        return list(
            (
                await db.execute(
                    select(Tenant.id).where(Tenant.status == TenantStatus.ACTIVE)
                )
            ).scalars().all()
        )


async def _process_tenant(tenant_id) -> tuple[int, int]:
    processed = 0
    failures = 0
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = tenant_id
        await db.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
        job_ids = await due_signing_job_ids(db, tenant_id=tenant_id, limit=100)
        for job_id in job_ids:
            try:
                result = await process_signing_job(db, tenant_id=tenant_id, job_id=job_id)
                processed += int(result.changed)
                logger.info("tenant=%s job=%s status=%s", tenant_id, job_id, result.status)
            except Exception:
                # Service-level provider/domain errors are persisted as job state;
                # this guard isolates truly unexpected failures so one job never
                # prevents the remaining tenant queue from being attempted.
                failures += 1
                logger.exception("Unexpected signing worker failure tenant=%s job=%s", tenant_id, job_id)
    return processed, failures


async def main() -> None:
    total_processed = 0
    total_failures = 0
    for tenant_id in await _active_tenants():
        processed, failures = await _process_tenant(tenant_id)
        total_processed += processed
        total_failures += failures
    logger.info("certificate signing worker complete processed=%s unexpected_failures=%s", total_processed, total_failures)


if __name__ == "__main__":
    asyncio.run(main())
