import asyncio
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.core.database import Base
from app.core.security import hash_password
from app.main import app
from fastapi.testclient import TestClient
from app.models.user import User, UserRole

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def async_engine():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture
async def async_session(async_engine):
    async_session_maker = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_maker() as session:
        yield session

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def admin_token():
    """Garante um usuário admin no banco de dados real e retorna o token."""
    email = "testadmin@example.com"
    password = "admin123"
    cpf = "11122233344"

    from app.core.database import AsyncSessionLocal

    async def ensure_admin():
        async with AsyncSessionLocal() as session:
            stmt = select(User).where(User.email == email)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                user = User(
                    email=email,
                    full_name="Test Admin",
                    cpf=cpf,
                    password_hash=hash_password(password),
                    role=UserRole.ADMIN,
                    is_active=True,
                )
                session.add(user)
            else:
                user.role = UserRole.ADMIN
                user.password_hash = hash_password(password)

            await session.commit()

    asyncio.run(ensure_admin())

    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]

@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}

@pytest.fixture
def test_user_data():
    return {
        "email": "test@example.com",
        "full_name": "Test User",
        "password": "testpassword123",
    }

@pytest.fixture
def test_course_data():
    return {
        "code": "NR-10",
        "name": "Segurança em Instalações Elétricas",
        "category": "Segurança",
        "carga_horaria": 40,
        "modality": "PRESENCIAL",
        "price": 500.00,
        "description": "Curso de segurança em instalações elétricas",
    }
