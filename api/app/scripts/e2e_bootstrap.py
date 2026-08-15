#!/usr/bin/env python3
"""Bootstrap idempotente para testes E2E full-stack.

Cria APENAS os dados mínimos necessários para o teste de integração
Playwright executar contra um banco recém-migrado:

- Usuário ADMIN (admin@wrcursos.com.br / admin123) no tenant WR

PROTEÇÃO:
- Só executa se E2E_TEST_MODE=true (env var).
- Recusa executar se E2E_TEST_MODE não estiver definido ou for falsy.
- Idempotente: se o usuário já existe, não faz nada.

NÃO criar credenciais de teste no fluxo de produção.
NÃO expor endpoint HTTP público.
Usa hash real da aplicação (app.core.security.hash_password).

Uso:
    E2E_TEST_MODE=true python -m app.scripts.e2e_bootstrap
"""

import asyncio
import os
import sys

from sqlalchemy import select, text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole

ADMIN_EMAIL = "admin@wrcursos.com.br"
ADMIN_CPF = "12345678901"
ADMIN_PASSWORD = "admin123"
ADMIN_FULL_NAME = "Administrador WR"


def _is_e2e_mode() -> bool:
    return os.environ.get("E2E_TEST_MODE", "").lower() in ("true", "1", "yes")


async def bootstrap_e2e_admin() -> dict:
    """Cria o admin de E2E se não existir. Retorna relatório."""
    report = {"created": False, "already_exists": False, "email": ADMIN_EMAIL}

    # Sessão privilegiada (bypass_rls) para garantir acesso ao tenant WR
    db = AsyncSessionLocal()
    db.info["tenant_id"] = WR_TENANT_ID
    try:
        await db.execute(
            text(f"SET LOCAL app.current_tenant = '{WR_TENANT_ID}'")
        )
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))

        existing = (
            await db.execute(select(User).where(User.email == ADMIN_EMAIL))
        ).scalar_one_or_none()

        if existing:
            report["already_exists"] = True
            return report

        admin = User(
            email=ADMIN_EMAIL,
            cpf=ADMIN_CPF,
            full_name=ADMIN_FULL_NAME,
            password_hash=hash_password(ADMIN_PASSWORD),
            role=UserRole.ADMIN,
        )
        db.add(admin)
        await db.commit()
        report["created"] = True
        return report
    finally:
        await db.close()


def main():
    if not _is_e2e_mode():
        print(
            "ERROR: E2E_TEST_MODE is not set to 'true'. "
            "This script must only run in test environments.",
            file=sys.stderr,
        )
        sys.exit(1)

    report = asyncio.run(bootstrap_e2e_admin())
    if report["created"]:
        print(f"✓ E2E admin created: {report['email']}")
    elif report["already_exists"]:
        print(f"✓ E2E admin already exists: {report['email']}")
    else:
        print(f"Unexpected state: {report}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
