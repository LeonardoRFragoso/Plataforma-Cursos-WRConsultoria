import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.database import Base
from app.main import app
from fastapi.testclient import TestClient

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
        "modality": "presencial",
        "price": 500.00,
        "description": "Curso de segurança em instalações elétricas",
    }
