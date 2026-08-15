"""Script idempotente de migração pós-deploy: move
``tenant.settings["mp_access_token"]`` (plaintext) para ``TenantSecret``
(criptografado) e remove a chave plaintext de ``settings``.

Requer que ``TENANT_SECRET_ENCRYPTION_KEY`` (ou ``SECRET_KEY`` como
fallback de desenvolvimento) esteja definida no ambiente de execução.

Uso:

    cd api && python -m app.scripts.migrate_mp_access_tokens

O script:
1. detecta tenants com ``settings.mp_access_token`` não vazio;
2. criptografa o valor em ``TenantSecret`` (key=mercado_pago_access_token);
3. verifica persistência descriptografando;
4. remove a chave ``mp_access_token`` de ``settings``;
5. é idempotente — pode ser executado novamente sem duplicação.

A chave Fernet NUNCA é hardcoded no repositório; é lida da configuração
de ambiente.
"""

import asyncio
import sys

from sqlalchemy import select

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.models.tenant import Tenant
from app.models.tenant_secret import TenantSecret
from app.services.secret_crypto import decrypt
from app.services.tenant_secret_service import (
    MERCADO_PAGO_ACCESS_TOKEN_KEY,
    set_tenant_secret,
)


async def migrate_tenant_mp_tokens(dry_run: bool = False) -> dict:
    """Executa a migração e retorna um relatório estruturado."""
    report = {
        "scanned": 0,
        "migrated": 0,
        "already_migrated": 0,
        "skipped_empty": 0,
        "errors": [],
        "tenants_migrated": [],
    }

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        result = await db.execute(
            select(Tenant).where(Tenant.settings.isnot(None))
        )
        tenants = result.scalars().all()
        report["scanned"] = len(tenants)

        for tenant in tenants:
            settings = tenant.settings or {}
            plaintext = settings.get("mp_access_token")
            if not plaintext:
                report["skipped_empty"] += 1
                continue

            # Verifica se já existe um TenantSecret para essa key
            existing = (
                await db.execute(
                    select(TenantSecret).where(
                        TenantSecret.tenant_id == tenant.id,
                        TenantSecret.key == MERCADO_PAGO_ACCESS_TOKEN_KEY,
                    )
                )
            ).scalar_one_or_none()

            if existing:
                # Verifica se o valor existente corresponde ao plaintext
                try:
                    existing_value = decrypt(existing.encrypted_value)
                except ValueError:
                    existing_value = None
                if existing_value == plaintext:
                    # Já migrado corretamente — apenas remove o plaintext
                    if not dry_run:
                        new_settings = {k: v for k, v in settings.items() if k != "mp_access_token"}
                        tenant.settings = new_settings
                        await db.commit()
                    report["already_migrated"] += 1
                    report["tenants_migrated"].append(str(tenant.id))
                    continue

            # Criptografa e persiste
            if not dry_run:
                await set_tenant_secret(
                    db,
                    tenant.id,
                    MERCADO_PAGO_ACCESS_TOKEN_KEY,
                    plaintext,
                    description="Migrated from tenant.settings (legacy)",
                )
                # Verifica persistência descriptografando
                stored = (
                    await db.execute(
                        select(TenantSecret).where(
                            TenantSecret.tenant_id == tenant.id,
                            TenantSecret.key == MERCADO_PAGO_ACCESS_TOKEN_KEY,
                        )
                    )
                ).scalar_one()
                try:
                    verified = decrypt(stored.encrypted_value)
                except ValueError as exc:
                    report["errors"].append(
                        f"tenant {tenant.id}: verification failed: {exc}"
                    )
                    continue
                if verified != plaintext:
                    report["errors"].append(
                        f"tenant {tenant.id}: plaintext mismatch after encrypt"
                    )
                    continue
                # Remove a chave plaintext de settings (reatribui para
                # forçar tracking de mutação do JSON column)
                new_settings = {k: v for k, v in settings.items() if k != "mp_access_token"}
                tenant.settings = new_settings
                await db.commit()
            report["migrated"] += 1
            report["tenants_migrated"].append(str(tenant.id))

    return report


def main():
    dry_run = "--dry-run" in sys.argv
    print(f"Starting mp_access_token migration (dry_run={dry_run})...")
    report = asyncio.run(migrate_tenant_mp_tokens(dry_run=dry_run))
    print(f"Scanned: {report['scanned']}")
    print(f"Migrated: {report['migrated']}")
    print(f"Already migrated (plaintext removed): {report['already_migrated']}")
    print(f"Skipped (empty): {report['skipped_empty']}")
    if report["errors"]:
        print("Errors:")
        for err in report["errors"]:
            print(f"  - {err}")
        sys.exit(1)
    print("Migration complete.")


if __name__ == "__main__":
    main()
