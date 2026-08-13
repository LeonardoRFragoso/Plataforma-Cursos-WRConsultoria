import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
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

router = APIRouter()

def is_cpf(identifier: str) -> bool:
    """Verifica se o identificador é um CPF (apenas números, 11 dígitos)"""
    cpf_pattern = r'^\d{11}$'
    return bool(re.match(cpf_pattern, identifier.replace('.', '').replace('-', '')))

def is_email(identifier: str) -> bool:
    """Verifica se o identificador é um e-mail"""
    email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    return bool(re.match(email_pattern, identifier))

@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.email == user_data.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    if user_data.cpf:
        stmt = select(User).where(User.cpf == user_data.cpf)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CPF already registered",
            )
    
    user = User(
        email=user_data.email,
        cpf=user_data.cpf,
        full_name=user_data.full_name,
        password_hash=hash_password(user_data.password),
        role=UserRole.STUDENT,
    )
    db.add(user)
    await db.flush()
    
    # Criar Student automaticamente se o CPF foi informado
    if user_data.cpf:
        student = Student(
            user_id=user.id,
            cpf=user_data.cpf,
            phone=None,
            company=None,
            address=None,
            city=None,
            state=None,
            zip_code=None,
        )
        db.add(student)
    
    await db.commit()
    await db.refresh(user)
    return user

@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    Login com CPF ou e-mail.
    Aceita identifier como CPF (11 dígitos) ou e-mail.
    """
    user = None
    
    if is_cpf(credentials.identifier):
        stmt = select(User).where(User.cpf == credentials.identifier)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
    elif is_email(credentials.identifier):
        stmt = select(User).where(User.email == credentials.identifier)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Identifier must be a valid CPF (11 digits) or email",
        )
    
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )
    
    access_token = create_access_token({"sub": str(user.id), "role": user.role})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    
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
    
    stmt = select(User).where(User.id == UUID(user_id))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    access_token = create_access_token({"sub": user_id, "role": user.role})
    refresh_token = create_refresh_token({"sub": user_id, "role": user.role})
    
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
