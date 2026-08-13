import pytest
import httpx
from app.core.config import settings

settings.DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/wr_cursos_test"

from app.core.database import Base, AsyncSessionLocal, engine
from app.core.security import hash_password
from app.main import app
from app.models.user import User, UserRole


@pytest.fixture(autouse=True, scope="function")
async def setup_db():
    """Recria o esquema do banco para cada teste."""
    await engine.dispose()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture
async def admin_token(client):
    """Cria um usuário admin e autentica, retornando o access token."""
    email = "testadmin@example.com"
    password = "admin123"
    cpf = "11122233344"

    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            full_name="Test Admin",
            cpf=cpf,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(user)
        await session.commit()

    response = await client.post(
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
