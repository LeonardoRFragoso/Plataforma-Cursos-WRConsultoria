"""Central WR SSO receiver — LMS side.

The LMS acts as a Service Provider (SP) and the Central WR platform as the
Identity Provider (IdP). After the user authenticates at Central WR, the
browser is redirected to the LMS frontend callback page (``/sso/callback``)
with a ``code`` and ``state`` query parameter. The frontend posts those to
this endpoint, which exchanges the code server-to-server with the Central WR
backend and issues the LMS's own JWT tokens.

Only Central WR ``ADMIN`` users are accepted (mapped to LMS ``admin``).
Other roles are rejected with 403.
"""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import WR_TENANT_ID
from app.core.database import get_db
from app.core.normalization import normalize_email
from app.core.security import create_access_token, create_refresh_token
from app.models.external_identity import ExternalIdentity
from app.models.user import User, UserRole
from app.schemas.sso import SsoCallbackRequest, SsoCallbackResponse

logger = logging.getLogger("app.sso")

router = APIRouter()

SSO_PROVIDER = "central-wr"

# Central WR role → LMS role mapping. Only ADMIN is accepted for now.
_CENTRAL_ROLE_MAP = {
    "ADMIN": UserRole.ADMIN,
}


class CentralWrExchangeError(Exception):
    """Raised when the server-to-server exchange with Central WR fails."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def _exchange_code_with_central(
    code: str,
    target_application: str,
) -> dict:
    """Call the Central WR backend to exchange the authorization code.

    Returns the identity claims dict on success. Raises
    ``CentralWrExchangeError`` on any non-2xx response or network error.
    """
    payload = {
        "client_id": settings.CENTRAL_WR_SSO_CLIENT_ID,
        "client_secret": settings.CENTRAL_WR_SSO_CLIENT_SECRET,
        "code": code,
        "target_application": target_application,
    }
    url = f"{settings.CENTRAL_WR_BACKEND_URL.rstrip('/')}/api/v1/sso/lms/exchange"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        logger.warning(
            "sso_exchange_network_error",
            extra={"event": "sso_login_failed", "reason": "network_error"},
        )
        raise CentralWrExchangeError(
            status.HTTP_502_BAD_GATEWAY,
            "Não foi possível conectar à Central WR",
        ) from exc

    if response.status_code != 200:
        # Propagate the Central WR error detail when available, but never log
        # the code/secret/tokens.
        detail = "Código de autorização inválido ou expirado"
        try:
            body = response.json()
            if isinstance(body, dict) and body.get("detail"):
                detail = str(body["detail"])
        except (ValueError, TypeError):
            pass
        logger.warning(
            "sso_exchange_rejected",
            extra={
                "event": "sso_login_failed",
                "reason": "central_rejected",
                "central_status": response.status_code,
            },
        )
        # Map Central WR 400 (expired/invalid code) → 400 on the LMS side.
        mapped_status = (
            status.HTTP_400_BAD_REQUEST
            if response.status_code in (400, 401, 404)
            else status.HTTP_502_BAD_GATEWAY
        )
        raise CentralWrExchangeError(mapped_status, detail)

    try:
        claims = response.json()
    except (ValueError, TypeError) as exc:
        logger.warning(
            "sso_exchange_bad_payload",
            extra={"event": "sso_login_failed", "reason": "bad_payload"},
        )
        raise CentralWrExchangeError(
            status.HTTP_502_BAD_GATEWAY,
            "Resposta inválida da Central WR",
        ) from exc

    return claims


def _map_role(central_role: str) -> UserRole:
    """Map a Central WR role to an LMS role.

    Only ``ADMIN`` is accepted. Any other role is rejected with 403.
    """
    normalized = (central_role or "").strip().upper()
    lms_role = _CENTRAL_ROLE_MAP.get(normalized)
    if lms_role is None:
        logger.warning(
            "sso_role_not_allowed",
            extra={
                "event": "sso_login_failed",
                "reason": "role_not_allowed",
                "central_role": normalized,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores podem acessar via SSO",
        )
    return lms_role


@router.post("/exchange", response_model=SsoCallbackResponse)
async def sso_exchange(
    body: SsoCallbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SsoCallbackResponse:
    """Exchange a Central WR SSO authorization code for LMS tokens.

    Flow:
    1. Call Central WR backend server-to-server to exchange the code for
       identity claims.
    2. Map the Central role → LMS role (ADMIN only).
    3. Find or create the local user:
       a. Look up ``ExternalIdentity`` by provider + external_subject.
       b. If not found, look up by email within the WR tenant and link.
       c. If still not found, auto-provision a new admin user.
    4. Issue LMS JWT tokens (same shape as normal login).
    5. Update ``ExternalIdentity.last_login_at``.
    """
    # Exchange the code with Central WR.
    try:
        claims = await _exchange_code_with_central(body.code, body.target_application)
    except CentralWrExchangeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    external_subject = claims.get("sub")
    email = claims.get("email")
    name = claims.get("name") or "Usuário Central WR"
    central_role = claims.get("role", "")

    if not external_subject or not email:
        logger.warning(
            "sso_exchange_missing_claims",
            extra={"event": "sso_login_failed", "reason": "missing_claims"},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Resposta inválida da Central WR",
        )

    # Map the role (raises 403 for non-ADMIN).
    lms_role = _map_role(central_role)

    normalized_email = normalize_email(email)

    # 1. Look up existing ExternalIdentity link.
    stmt = select(ExternalIdentity).where(
        ExternalIdentity.provider == SSO_PROVIDER,
        ExternalIdentity.external_subject == str(external_subject),
    )
    result = await db.execute(stmt)
    ext_identity = result.scalar_one_or_none()

    user: User | None = None
    linked_new_identity = False
    provisioned = False

    if ext_identity:
        # Existing link — fetch the user.
        user_stmt = select(User).where(User.id == ext_identity.user_id)
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()
        if user and not user.is_active:
            logger.warning(
                "sso_login_inactive_user",
                extra={
                    "event": "sso_login_failed",
                    "reason": "inactive",
                    "user_id": str(user.id),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuário inativo",
            )
    else:
        # 2. No external link — try to match by email within the WR tenant.
        email_stmt = select(User).where(
            User.email == normalized_email,
            User.tenant_id == WR_TENANT_ID,
        )
        email_result = await db.execute(email_stmt)
        user = email_result.scalar_one_or_none()

        if user:
            if not user.is_active:
                logger.warning(
                    "sso_login_inactive_user",
                    extra={
                        "event": "sso_login_failed",
                        "reason": "inactive",
                        "user_id": str(user.id),
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Usuário inativo",
                )
            # Link the external identity to the existing user.
            ext_identity = ExternalIdentity(
                provider=SSO_PROVIDER,
                external_subject=str(external_subject),
                user_id=user.id,
                tenant_id=user.tenant_id,
            )
            db.add(ext_identity)
            linked_new_identity = True
        else:
            # 3. Auto-provision a new admin user (no password — SSO only).
            user = User(
                tenant_id=WR_TENANT_ID,
                email=normalized_email,
                full_name=name,
                password_hash=None,
                role=lms_role,
                is_active=True,
            )
            db.add(user)
            await db.flush()
            ext_identity = ExternalIdentity(
                provider=SSO_PROVIDER,
                external_subject=str(external_subject),
                user_id=user.id,
                tenant_id=user.tenant_id,
            )
            db.add(ext_identity)
            provisioned = True

    # Update last login timestamp.
    from app.core.utils import utc_now

    ext_identity.last_login_at = utc_now()

    await db.commit()
    await db.refresh(user)

    # Issue LMS tokens.
    token_data = {
        "sub": str(user.id),
        "role": user.role,
        "tenant_id": str(user.tenant_id),
    }
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Structured logging — never log tokens, codes, or secrets.
    if provisioned:
        logger.info(
            "sso_account_provisioned",
            extra={
                "event": "sso_account_provisioned",
                "user_id": str(user.id),
                "provider": SSO_PROVIDER,
            },
        )
    elif linked_new_identity:
        logger.info(
            "sso_account_linked",
            extra={
                "event": "sso_account_linked",
                "user_id": str(user.id),
                "provider": SSO_PROVIDER,
            },
        )
    logger.info(
        "sso_login_success",
        extra={
            "event": "sso_login_success",
            "user_id": str(user.id),
            "provider": SSO_PROVIDER,
        },
    )

    return SsoCallbackResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )
