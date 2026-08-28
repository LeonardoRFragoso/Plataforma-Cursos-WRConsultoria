"""Bootstrap a B2B API client for Central WR.

Creates (or updates in dev) a B2BClient record that Central WR uses
to query academic data from the LMS in read-only mode.

Usage::

    python -m app.scripts.bootstrap_b2b_client

Reads from environment:
- B2B_CENTRAL_WR_CLIENT_ID (required in production, defaults in dev)
- B2B_CENTRAL_WR_CLIENT_SECRET (required, >=32 chars, never printed)
- B2B_CENTRAL_WR_TENANT_SLUG (required in production, defaults in dev)

The secret is hashed before storage. In development, re-running the
script updates the secret if the client already exists. In production,
existing clients are never modified (only created if missing).

Error handling:
- All error paths exit with non-zero status code.
- The secret is NEVER printed or logged.
- In production, all three env vars are mandatory.
"""

import asyncio
import os
import sys

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.b2b_client import B2BClient
from app.models.tenant import Tenant

_WEAK_SECRET_PATTERNS = ("changeme", "secret", "password", "default", "example", "placeholder")


def _is_weak_secret(secret: str) -> bool:
    lower = secret.lower()
    return any(p in lower for p in _WEAK_SECRET_PATTERNS)


async def bootstrap() -> int:
    is_dev = settings.ENVIRONMENT.lower() in ("development", "test", "dev")

    client_id = os.environ.get("B2B_CENTRAL_WR_CLIENT_ID", "")
    client_secret = os.environ.get("B2B_CENTRAL_WR_CLIENT_SECRET", "")
    tenant_slug = os.environ.get("B2B_CENTRAL_WR_TENANT_SLUG", "")

    if is_dev:
        client_id = client_id or "central-wr-b2b"
        tenant_slug = tenant_slug or "wr"

    if not client_id:
        print("ERROR: B2B_CENTRAL_WR_CLIENT_ID must be set", file=sys.stderr)
        return 2
    if not client_secret:
        print("ERROR: B2B_CENTRAL_WR_CLIENT_SECRET must be set", file=sys.stderr)
        return 2
    if len(client_secret) < 32:
        print("ERROR: B2B_CENTRAL_WR_CLIENT_SECRET must be at least 32 characters", file=sys.stderr)
        return 2
    if _is_weak_secret(client_secret):
        print("ERROR: B2B_CENTRAL_WR_CLIENT_SECRET appears to be a default/weak value", file=sys.stderr)
        return 2
    if not tenant_slug:
        print("ERROR: B2B_CENTRAL_WR_TENANT_SLUG must be set", file=sys.stderr)
        return 2

    async with AsyncSessionLocal() as db:
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
        if tenant is None:
            print(f"ERROR: Tenant '{tenant_slug}' not found", file=sys.stderr)
            return 1

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

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(bootstrap()))
