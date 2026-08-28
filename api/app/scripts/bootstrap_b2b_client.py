"""Bootstrap a B2B API client for Central WR.

Creates (or updates in dev) a B2BClient record that Central WR uses
to query academic data from the LMS in read-only mode.

Usage::

    python -m app.scripts.bootstrap_b2b_client

Reads from settings:
- B2B_CENTRAL_WR_CLIENT_ID
- B2B_CENTRAL_WR_CLIENT_SECRET
- B2B_CENTRAL_WR_TENANT_SLUG (defaults to "wr")

The secret is hashed before storage. In development, re-running the
script updates the secret if the client already exists. In production,
existing clients are never modified (only created if missing).
"""

import asyncio
import os

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.b2b_client import B2BClient
from app.models.tenant import Tenant


async def bootstrap() -> None:
    client_id = os.environ.get("B2B_CENTRAL_WR_CLIENT_ID", "central-wr-b2b")
    client_secret = os.environ.get("B2B_CENTRAL_WR_CLIENT_SECRET", "")
    tenant_slug = os.environ.get("B2B_CENTRAL_WR_TENANT_SLUG", "wr")
    is_dev = settings.ENVIRONMENT.lower() in ("development", "test", "dev")

    if not client_secret:
        print("ERROR: B2B_CENTRAL_WR_CLIENT_SECRET must be set")
        return

    async with AsyncSessionLocal() as db:
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
        if tenant is None:
            print(f"ERROR: Tenant '{tenant_slug}' not found")
            return

        client = await db.scalar(select(B2BClient).where(B2BClient.client_id == client_id))
        if client is None:
            client = B2BClient(
                tenant_id=tenant.id,
                client_id=client_id,
                client_secret_hash=hash_password(client_secret),
                name="Central WR B2B",
                allowed_scopes="academic:read",
                is_active=True,
            )
            db.add(client)
            print(f"Created B2B client '{client_id}' for tenant '{tenant_slug}'")
        elif is_dev:
            client.client_secret_hash = hash_password(client_secret)
            client.allowed_scopes = "academic:read"
            client.is_active = True
            print(f"Updated B2B client '{client_id}' (dev mode)")
        else:
            print(f"B2B client '{client_id}' already exists (production — not modified)")
        await db.commit()


if __name__ == "__main__":
    asyncio.run(bootstrap())
