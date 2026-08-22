"""Serviço de acesso a secrets criptografados de tenant.

Centraliza a leitura de secrets de tenant para consumidores backend
(ex.: gateway de pagamento Mercado Pago). O valor descriptografado nunca
é exposto em responses ou logs — apenas retornado ao código backend
autorizado.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import WR_TENANT_ID
from app.models.tenant_secret import TenantSecret
from app.services.secret_crypto import decrypt

# Chaves canônicas de secrets de tenant.
MERCADO_PAGO_ACCESS_TOKEN_KEY = "mercado_pago_access_token"
ASAAS_API_KEY_KEY = "asaas_api_key"


async def get_tenant_secret(
    db: AsyncSession,
    tenant_id: UUID,
    key: str,
) -> str | None:
    """Retorna o valor plano de um secret de tenant.

    Consulta TenantSecret, descriptografa internamente e retorna o valor
    somente ao código backend autorizado. Nunca expõe o valor em
    responses ou logs. Retorna None se o secret não existir.
    """
    stmt = select(TenantSecret).where(
        TenantSecret.tenant_id == tenant_id,
        TenantSecret.key == key,
    )
    result = await db.execute(stmt)
    secret = result.scalar_one_or_none()
    if not secret:
        return None
    try:
        return decrypt(secret.encrypted_value)
    except ValueError:
        # Secret corrompido/inválido — trata como ausente para não vazar
        # detalhes de criptografia em logs.
        return None


async def get_mercado_pago_access_token(
    db: AsyncSession,
    tenant_id: UUID,
) -> str | None:
    """Atalho para obter o access token do Mercado Pago do tenant."""
    return await get_tenant_secret(
        db, tenant_id, MERCADO_PAGO_ACCESS_TOKEN_KEY
    )


async def get_asaas_api_key(
    db: AsyncSession,
    tenant_id: UUID,
) -> str | None:
    """Atalho para obter a API key do Asaas do tenant."""
    return await get_tenant_secret(db, tenant_id, ASAAS_API_KEY_KEY)


async def set_tenant_secret(
    db: AsyncSession,
    tenant_id: UUID,
    key: str,
    value: str,
    description: str | None = None,
) -> TenantSecret:
    """Cria ou atualiza um secret de tenant (idempotente em key)."""
    stmt = select(TenantSecret).where(
        TenantSecret.tenant_id == tenant_id,
        TenantSecret.key == key,
    )
    result = await db.execute(stmt)
    secret = result.scalar_one_or_none()
    if secret:
        from app.services.secret_crypto import encrypt

        secret.encrypted_value = encrypt(value)
        if description is not None:
            secret.description = description
    else:
        from app.services.secret_crypto import encrypt

        secret = TenantSecret(
            tenant_id=tenant_id,
            key=key,
            encrypted_value=encrypt(value),
            description=description,
        )
        db.add(secret)
    await db.flush()
    return secret


# Constante de conveniência para o tenant WR.
WR_TENANT = WR_TENANT_ID
