"""Periodic reconciliation command intended for Railway cron/operations.

This command performs provider status reads only. It does not create charges or
initiate refunds. Schedule it externally (for example hourly) when production
credentials are activated.

Run from ``api``:
    python -m app.scripts.reconcile_payments
"""

from __future__ import annotations

import asyncio
import json

from sqlalchemy import select, text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.models.tenant import Tenant, TenantStatus
from app.services.periodic_payment_reconciliation import reconcile_tenant_payments


async def _active_tenant_ids():
    """Read all active tenants through the same privileged RLS contract used by the API."""
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await db.execute(text(f"SET LOCAL app.current_tenant = '{WR_TENANT_ID}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        tenants = (
            await db.execute(select(Tenant.id).where(Tenant.status == TenantStatus.ACTIVE))
        ).scalars().all()
        return list(tenants)


async def main() -> None:
    results = []
    for tenant_id in await _active_tenant_ids():
        async with AsyncSessionLocal() as db:
            db.info["tenant_id"] = tenant_id
            await db.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
            try:
                result = await reconcile_tenant_payments(db, tenant_id)
                results.append({"tenant_id": str(tenant_id), "ok": True, **result})
            except Exception as exc:
                await db.rollback()
                # Do not serialize provider bodies, credentials or PII.
                results.append(
                    {
                        "tenant_id": str(tenant_id),
                        "ok": False,
                        "error": type(exc).__name__,
                    }
                )
    print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
