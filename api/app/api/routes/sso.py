"""Central WR SSO receiver — LMS side.

The LMS acts as a Service Provider (SP) and the Central WR platform as the
Identity Provider (IdP). After the user authenticates at Central WR, the
browser is redirected to the LMS frontend callback page (``/sso/callback``)
with a ``code`` and ``state`` query parameter. The frontend posts those to
this endpoint, which exchanges the code server-to-server with the Central WR
backend and issues the LMS's own JWT tokens.

Only Central WR ``ADMIN`` users are accepted (mapped to LMS ``admin``).
Other roles are rejected with 403.

Role reconciliation:
- Central ADMIN + LMS admin → stays admin.
- Central ADMIN + LMS student → rejected with 403; never promoted.
- Central ADMIN + LMS super_admin → stays super_admin (never downgraded).
- Central ADMIN + no LMS user → auto-provisioned as admin.
- Central non-ADMIN → 403, no role change.

Claim validation (defense in depth, before any user provisioning):
- ``source`` must be ``"central-wr"``.
- ``role`` must be ``"ADMIN"``.
- ``tenant_id`` must be present.
- ``tenant_id`` must match ``CENTRAL_WR_TRUSTED_TENANT_ID``. In production
  this setting is required (non-empty, valid UUID) — the config validator
  blocks startup if it is missing, so the check can never be silently
  disabled. In development/test it may be empty to allow local testing.
"""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
_EXPECTED_SOURCE = "central-wr"

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
    state: str,
    target_application: str,
) -> dict:
    """Call the Central WR backend to exchange the authorization code.

    The ``state`` (nonce) is sent to Central WR which validates it against
    the ticket's nonce before consuming the code. This prevents CSRF and
    code injection attacks.

    Returns the identity claims dict on success. Raises
    ``CentralWrExchangeError`` on any non-2xx response or network error.
    """
    payload = {
        "client_id": settings.CENTRAL_WR_SSO_CLIENT_ID,
        "client_secret": settings.CENTRAL_WR_SSO_CLIENT_SECRET,
        "code": code,
        "state": state,
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
        # Map Central WR 400 (expired/invalid code/state) → 400 on the LMS side.
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


def _validate_claims(claims: dict) -> None:
    """Validate the identity claims returned by Central WR.

    This is defense in depth — even if Central WR is compromised or a bug
    causes it to return unexpected claims, the LMS must not provision or
    link any user.

    Raises HTTPException (403 or 502) on any validation failure.
    """
    source = claims.get("source")
    if source != _EXPECTED_SOURCE:
        logger.warning(
            "sso_claims_invalid_source",
            extra={
                "event": "sso_login_failed",
                "reason": "invalid_source",
                "source": source,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origem de identidade não confiável",
        )

    central_role = (claims.get("role") or "").strip().upper()
    if central_role != "ADMIN":
        logger.warning(
            "sso_claims_role_not_allowed",
            extra={
                "event": "sso_login_failed",
                "reason": "role_not_allowed",
                "central_role": central_role,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores podem acessar via SSO",
        )

    central_tenant_id = claims.get("tenant_id")
    if not central_tenant_id:
        logger.warning(
            "sso_claims_missing_tenant",
            extra={
                "event": "sso_login_failed",
                "reason": "missing_tenant",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Resposta inválida da Central WR",
        )

    # If CENTRAL_WR_TRUSTED_TENANT_ID is configured, validate that the
    # Central WR tenant_id matches it. This prevents an ADMIN from a
    # different Central WR tenant from getting SSO access.
    trusted = settings.CENTRAL_WR_TRUSTED_TENANT_ID
    if trusted and str(central_tenant_id) != str(trusted):
        logger.warning(
            "sso_claims_tenant_not_trusted",
            extra={
                "event": "sso_login_failed",
                "reason": "tenant_not_trusted",
                "central_tenant_id": central_tenant_id,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant da Central WR não autorizado",
        )


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


def _reconcile_role(user: User, central_role: str) -> bool:
    """Reconcile the LMS user's role based on the Central WR role.

    Rules:
    - Central ADMIN + LMS admin → stays admin (no change).
    - Central ADMIN + LMS student → rejected; never promoted.
    - Central ADMIN + LMS super_admin → stays super_admin (NEVER downgraded).
    - Central non-ADMIN → caller must have already rejected with 403.

    Returns True if the role was changed, False if it stayed the same.
    Raises 403 for an existing local user without an administrative role.
    """
    normalized_central = (central_role or "").strip().upper()
    if normalized_central != "ADMIN":
        # Should never reach here — _map_role already rejected non-ADMIN.
        return False

    if user.role == UserRole.SUPER_ADMIN:
        # Never downgrade super_admin.
        return False

    if user.role != UserRole.ADMIN:
        logger.warning(
            "sso_existing_user_role_not_allowed",
            extra={
                "event": "sso_login_failed",
                "reason": "existing_user_not_admin",
                "user_id": str(user.id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário local não possui perfil administrativo",
        )

    return False


@router.post("/exchange", response_model=SsoCallbackResponse)
async def sso_exchange(
    body: SsoCallbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SsoCallbackResponse:
    """Exchange a Central WR SSO authorization code for LMS tokens.

    Flow:
    1. Call Central WR backend server-to-server to exchange the code + state
       for identity claims. Central validates state == ticket.nonce.
    2. **Validate claims** (source, role, tenant_id, trusted tenant).
       This happens BEFORE any user lookup or provisioning — if claims
       are invalid, no user is created, no ExternalIdentity is linked,
       and no role is changed.
    3. Map the Central role → LMS role (ADMIN only, 403 otherwise).
    4. Find or create the local user:
       a. Look up ``ExternalIdentity`` by provider + external_subject.
       b. If not found, look up by email within the WR tenant and link.
       c. If still not found, auto-provision a new admin user.
    5. Reconcile role: existing local students are rejected; existing
       administrators retain their role. Never downgrade super_admin.
    6. Issue LMS JWT tokens (same shape as normal login).
    7. Update ``ExternalIdentity.last_login_at``.
    """
    # Exchange the code with Central WR (state is validated by Central).
    try:
        claims = await _exchange_code_with_central(
            body.code, body.state, body.target_application,
        )
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

    # Validate claims BEFORE any user provisioning or ExternalIdentity
    # creation. This is the critical defense-in-depth check — an ADMIN
    # from an unauthorized Central WR tenant must never get access.
    _validate_claims(claims)

    # Map the role (raises 403 for non-ADMIN).
    lms_role = _map_role(central_role)

    normalized_email = normalize_email(email)

    # 1. Look up existing ExternalIdentity link — scoped to WR tenant only.
    #    An ExternalIdentity from another tenant must never resolve to a
    #    local user via SSO. This is defense-in-depth on top of the
    #    Central WR tenant trust check in _validate_claims.
    stmt = select(ExternalIdentity).where(
        ExternalIdentity.provider == SSO_PROVIDER,
        ExternalIdentity.external_subject == str(external_subject),
        ExternalIdentity.tenant_id == WR_TENANT_ID,
    )
    result = await db.execute(stmt)
    ext_identity = result.scalar_one_or_none()

    user: User | None = None
    linked_new_identity = False
    provisioned = False
    role_changed = False

    if ext_identity:
        # Existing link — fetch the user and verify tenant ownership.
        user_stmt = select(User).where(User.id == ext_identity.user_id)
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()
        if user and user.tenant_id != WR_TENANT_ID:
            logger.warning(
                "sso_login_cross_tenant_user",
                extra={
                    "event": "sso_login_failed",
                    "reason": "cross_tenant_user",
                    "user_id": str(user.id),
                    "user_tenant_id": str(user.tenant_id),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuário não pertence ao tenant esperado",
            )
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
        if user is None:
            # Orphan ExternalIdentity — identity points to a deleted user.
            # Fail closed; do not auto-provision or issue JWT.
            logger.warning(
                "sso_login_orphan_identity",
                extra={
                    "event": "sso_login_failed",
                    "reason": "orphan_identity",
                    "external_subject": str(external_subject),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Identidade externa órfã — contate o administrador",
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

    # 4. Reconcile role for existing users (promote student → admin,
    #    never downgrade super_admin). Only after Central confirmed identity.
    if not provisioned:
        role_changed = _reconcile_role(user, central_role)
        if role_changed:
            logger.info(
                "sso_role_reconciled",
                extra={
                    "event": "sso_role_reconciled",
                    "user_id": str(user.id),
                    "provider": SSO_PROVIDER,
                    "new_role": UserRole.ADMIN.value,
                },
            )

    # Update last login timestamp.
    from app.core.utils import utc_now

    ext_identity.last_login_at = utc_now()

    try:
        await db.commit()
    except IntegrityError as exc:
        # The unique constraint on (provider, external_subject) may fail
        # if the external_subject already exists in another tenant. This
        # is a cross-tenant SSO conflict — fail closed with 403.
        await db.rollback()
        logger.warning(
            "sso_login_identity_conflict",
            extra={
                "event": "sso_login_failed",
                "reason": "identity_conflict",
                "external_subject": str(external_subject),
                "detail": str(exc.orig),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conflito de identidade externa — contate o administrador",
        ) from exc
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
