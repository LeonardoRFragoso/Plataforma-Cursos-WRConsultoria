"""Secrets criptografados por tenant.

Tenant admins podem criar, atualizar, listar e remover seus próprios
secrets. O valor plano nunca é exposto nas respostas administrativas —
apenas metadados. A revelação do valor plano é exclusiva do SUPER_ADMIN
via /api/v1/super-admin/tenants/{tenant_id}/secrets/{id}/reveal.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id
from app.models.tenant_secret import TenantSecret
from app.schemas.tenant_secret import (
    TenantSecretCreate,
    TenantSecretResponse,
    TenantSecretUpdate,
)
from app.services.secret_crypto import encrypt

router = APIRouter()


@router.get("/", response_model=list[TenantSecretResponse])
async def list_secrets(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(TenantSecret).where(TenantSecret.tenant_id == tenant_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "/",
    response_model=TenantSecretResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_secret(
    data: TenantSecretCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    existing = (
        await db.execute(
            select(TenantSecret).where(
                TenantSecret.tenant_id == tenant_id,
                TenantSecret.key == data.key,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Secret with this key already exists",
        )
    secret = TenantSecret(
        tenant_id=tenant_id,
        key=data.key,
        encrypted_value=encrypt(data.value),
        description=data.description,
    )
    db.add(secret)
    await db.commit()
    await db.refresh(secret)
    return secret


@router.put("/{secret_id}", response_model=TenantSecretResponse)
async def update_secret(
    secret_id: UUID,
    data: TenantSecretUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    secret = await db.get(TenantSecret, secret_id)
    if not secret or secret.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Secret not found",
        )
    secret.encrypted_value = encrypt(data.value)
    if data.description is not None:
        secret.description = data.description
    await db.commit()
    await db.refresh(secret)
    return secret


@router.delete("/{secret_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_secret(
    secret_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    secret = await db.get(TenantSecret, secret_id)
    if not secret or secret.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Secret not found",
        )
    await db.delete(secret)
    await db.commit()
