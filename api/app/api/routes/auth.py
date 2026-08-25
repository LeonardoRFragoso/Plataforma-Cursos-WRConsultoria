from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import WR_TENANT_ID
from app.core.database import get_db
from app.core.normalization import (
    is_cpf_format,
    is_email_format,
    normalize_cpf,
    normalize_email,
    validate_cpf,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.user import (
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.services.email_service import EmailServiceError, get_email_service
from app.services.one_time_token_service import OneTimeTokenService
from app.services.transactional_notifications import send_welcome_notification


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ActivateRequest(BaseModel):
    token: str
    new_password: str


router = APIRouter()

# Environments where raw one-time tokens may be returned in responses.
# Only local development and automated test environments.
_LOCAL_TOKEN_RETURN_ENVS = frozenset({"development", "dev", "test", "testing"})

_GENERIC_RESET_RESPONSE = {"detail": "If the email exists, a reset link was sent"}


def _current_env() -> str:
    return getattr(settings, "ENVIRONMENT", "").lower()


def _can_return_token() -> bool:
    """Only local dev/test environments may return raw one-time tokens."""
    return _current_env() in _LOCAL_TOKEN_RETURN_ENVS


def _resolve_request_tenant_id(request: Request) -> UUID:
    """Resolve tenant_id from the request context set by TenantResolver."""
    scope_tenant = request.scope.get("resolved_tenant_id")
    if scope_tenant:
        try:
            return UUID(scope_tenant)
        except (ValueError, TypeError):
            pass

    state_tenant = getattr(request.state, "tenant_id", None)
    if state_tenant:
        return state_tenant

    return WR_TENANT_ID


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Public B2C registration, scoped to the resolved tenant."""
    resolved_tenant_id = _resolve_request_tenant_id(request)
    normalized_email = normalize_email(user_data.email)

    stmt = select(User).where(
        User.email == normalized_email,
        User.tenant_id == resolved_tenant_id,
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    try:
        cpf = validate_cpf(user_data.cpf)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CPF inválido",
        )

    stmt = select(User).where(
        User.cpf == cpf,
        User.tenant_id == resolved_tenant_id,
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CPF already registered",
        )

    user = User(
        tenant_id=resolved_tenant_id,
        email=normalized_email,
        cpf=cpf,
        full_name=user_data.full_name,
        password_hash=hash_password(user_data.password),
        role=UserRole.STUDENT,
    )
    db.add(user)
    await db.flush()

    student = Student(
        tenant_id=resolved_tenant_id,
        user_id=user.id,
        cpf=cpf,
        phone=None,
        company=None,
        address=None,
        city=None,
        state=None,
        zip_code=None,
    )
    db.add(student)

    # Account creation is authoritative. Notification is best-effort and runs
    # only after the registration transaction is durable.
    await db.commit()
    await db.refresh(user)
    await send_welcome_notification(db, user, resolved_tenant_id)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Login by CPF or email with tenant-scoped database lookup."""
    resolved_tenant_id = _resolve_request_tenant_id(request)
    user = None

    if is_cpf_format(credentials.identifier):
        cpf_digits = normalize_cpf(credentials.identifier)
        stmt = select(User).where(
            User.cpf == cpf_digits,
            User.tenant_id == resolved_tenant_id,
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
    elif is_email_format(credentials.identifier):
        normalized_email = normalize_email(credentials.identifier)
        stmt = select(User).where(
            User.email == normalized_email,
            User.tenant_id == resolved_tenant_id,
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Identifier must be a valid CPF (11 digits) or email",
        )

    if (
        not user
        or not user.password_hash
        or not verify_password(credentials.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    if user.role == UserRole.SUPER_ADMIN:
        if user.tenant_id != WR_TENANT_ID or resolved_tenant_id != WR_TENANT_ID:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
    elif user.tenant_id != resolved_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    access_token = create_access_token(
        {
            "sub": str(user.id),
            "role": user.role,
            "tenant_id": str(user.tenant_id),
        }
    )
    refresh_token = create_refresh_token(
        {
            "sub": str(user.id),
            "role": user.role,
            "tenant_id": str(user.tenant_id),
        }
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    payload = decode_token(request.refresh_token)
    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    from app.core.context import current_tenant_id

    resolved_tenant = current_tenant_id.get() or WR_TENANT_ID
    token_tenant_id = payload.get("tenant_id")
    if token_tenant_id:
        try:
            token_tenant_uuid = UUID(token_tenant_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
    else:
        token_tenant_uuid = None

    if token_tenant_uuid is not None and token_tenant_uuid != resolved_tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    stmt = select(User).where(User.id == UUID(user_id))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if user.tenant_id != resolved_tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    access_token = create_access_token(
        {
            "sub": user_id,
            "role": user.role,
            "tenant_id": str(user.tenant_id),
        }
    )
    refresh_token = create_refresh_token(
        {
            "sub": user_id,
            "role": user.role,
            "tenant_id": str(user.tenant_id),
        }
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User).where(User.id == current_user["user_id"])
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Request a tenant-scoped password reset link."""
    resolved_tenant_id = _resolve_request_tenant_id(request)
    normalized_email = normalize_email(payload.email)

    stmt = select(User).where(
        User.email == normalized_email,
        User.tenant_id == resolved_tenant_id,
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return dict(_GENERIC_RESET_RESPONSE)

    if user.role == UserRole.SUPER_ADMIN and resolved_tenant_id != WR_TENANT_ID:
        return dict(_GENERIC_RESET_RESPONSE)

    raw, _token = await OneTimeTokenService.create(
        db, str(user.id), "reset", ttl_hours=1
    )
    await db.commit()

    if _can_return_token():
        return {"reset_token": raw}

    try:
        email_service = get_email_service()
        await email_service.send_password_reset(
            to=user.email,
            reset_token=raw,
            frontend_url=settings.FRONTEND_URL,
            tenant_name="Plataforma",
        )
    except EmailServiceError:
        pass

    return dict(_GENERIC_RESET_RESPONSE)


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Reset password using a tenant-bound one-time token."""
    resolved_tenant_id = _resolve_request_tenant_id(request)

    token = await OneTimeTokenService.consume(db, payload.token, "reset")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )

    stmt = select(User).where(User.id == token.user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or user.tenant_id != resolved_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )

    user.password_hash = hash_password(payload.new_password)
    await db.commit()
    return {"detail": "Password reset successfully"}


@router.post("/activate")
async def activate(
    payload: ActivateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Activate an account using a tenant-bound one-time token."""
    resolved_tenant_id = _resolve_request_tenant_id(request)

    token = await OneTimeTokenService.consume(db, payload.token, "activation")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired activation token",
        )

    stmt = select(User).where(User.id == token.user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or user.tenant_id != resolved_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired activation token",
        )

    user.password_hash = hash_password(payload.new_password)
    user.is_active = True
    await db.commit()
    return {"detail": "Account activated successfully"}
