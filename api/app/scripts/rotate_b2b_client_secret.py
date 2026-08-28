"""Rotate a B2B client secret without exposing the old or new secret.

Usage::

    B2B_NEW_SECRET='...' python -m app.scripts.rotate_b2b_client_secret \
        --client-id central-wr-b2b

The new secret is accepted only through the environment (not a command-line
argument), validated for minimum entropy length, and stored as an Argon2 hash.
The plaintext is never logged or persisted by this script.
"""

import argparse
import asyncio
import os
import sys

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.b2b_client import B2BClient

_MIN_SECRET_LENGTH = 32


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rotate a B2B client secret")
    parser.add_argument("--client-id", required=True, help="Existing B2B client ID")
    return parser.parse_args()


async def rotate(client_id: str, new_secret: str) -> bool:
    """Replace a client's secret hash and return whether the client existed."""
    async with AsyncSessionLocal() as db:
        client = await db.scalar(
            select(B2BClient).where(B2BClient.client_id == client_id)
        )
        if client is None:
            return False
        client.client_secret_hash = hash_password(new_secret)
        await db.commit()
        return True


async def main() -> int:
    args = _parse_args()
    new_secret = os.environ.get("B2B_NEW_SECRET", "")
    if len(new_secret) < _MIN_SECRET_LENGTH:
        print(
            f"ERROR: B2B_NEW_SECRET must be at least {_MIN_SECRET_LENGTH} characters",
            file=sys.stderr,
        )
        return 2

    if not await rotate(args.client_id, new_secret):
        print(f"ERROR: B2B client '{args.client_id}' not found", file=sys.stderr)
        return 1

    print(f"Rotated secret for B2B client '{args.client_id}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
