import uuid
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import text

from app.core.config import settings

settings.DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/wr_cursos_test"

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal, Base, engine
from app.core.security import hash_password
from app.core.utils import utc_now
from app.main import app
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User, UserRole


async def _insert_master_tenant():
    async with AsyncSessionLocal() as session:
        existing = await session.get(Tenant, WR_TENANT_ID)
        if not existing:
            session.add(
                Tenant(
                    id=WR_TENANT_ID,
                    name="WR Consultoria e Soluções em QSMS",
                    slug="wr",
                    status=TenantStatus.ACTIVE,
                    contact_name="Admin WR",
                    contact_email="admin@wrconsultoriaesolucoes.com.br",
                )
            )
            await session.commit()


@pytest.fixture(autouse=True, scope="function")
async def setup_db():
    """Recria o esquema do banco para cada teste."""
    await engine.dispose()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("""
        DO $$
        DECLARE
            t text;
        BEGIN
            FOR t IN (
                SELECT typname
                FROM pg_type
                JOIN pg_namespace n ON n.oid = pg_type.typnamespace
                WHERE typtype = 'e' AND n.nspname = 'public'
            ) LOOP
                EXECUTE format('DROP TYPE IF EXISTS %I CASCADE', t);
            END LOOP;
        END $$;
        """))
        await conn.run_sync(Base.metadata.create_all)
    await _insert_master_tenant()
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
            tenant_id=WR_TENANT_ID,
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
async def super_admin_token(client):
    """Cria um usuário super_admin e autentica, retornando o access token."""
    email = "superadmin@example.com"
    password = "super123"

    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            full_name="Super Admin",
            cpf="99988877766",
            password_hash=hash_password(password),
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            tenant_id=WR_TENANT_ID,
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
def super_admin_headers(super_admin_token):
    return {"Authorization": f"Bearer {super_admin_token}"}


@pytest.fixture
def test_user_data():
    return {
        "email": "test@example.com",
        "full_name": "Test User",
        "password": "testpassword123",
        "cpf": "52988744005",
    }


@pytest.fixture
async def student_user(client, admin_headers):
    """Cria um aluno em uma turma e faz login, retornando headers e student_id."""
    email = f"student_{uuid.uuid4().hex[:8]}@example.com"
    cpf = f"{uuid.uuid4().int % 10**11:011d}"

    today = utc_now().date()
    course = await client.post(
        "/api/v1/courses/",
        json={
            "code": f"CUR-{uuid.uuid4().hex[:6].upper()}",
            "name": "Curso Teste",
            "category": "Segurança",
            "carga_horaria": 40,
            "modality": "PRESENCIAL",
            "price": 100.0,
            "description": "Curso teste",
        },
        headers=admin_headers,
    )
    assert course.status_code == 201
    course_id = course.json()["id"]

    me = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert me.status_code == 200
    admin_id = me.json()["id"]

    class_payload = {
        "course_id": course_id,
        "responsible_admin_id": admin_id,
        "start_date": (today + timedelta(days=1)).isoformat(),
        "end_date": (today + timedelta(days=30)).isoformat(),
        "max_students": 20,
        "location": "São Paulo",
        "ead_link": None,
        "status": "ABERTA",
        "description": "Turma teste",
    }
    class_response = await client.post("/api/v1/classes/", json=class_payload, headers=admin_headers)
    assert class_response.status_code == 201
    class_id = class_response.json()["id"]

    response = await client.post(
        "/api/v1/students/",
        json={
            "email": email,
            "full_name": "Aluno Teste",
            "password": "student123",
            "cpf": cpf,
            "phone": "(11) 99999-9999",
            "company": "Empresa Teste",
            "address": "Rua do Aluno, 123",
            "city": "São Paulo",
            "state": "SP",
            "zip_code": "01000-000",
            "class_id": class_id,
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    student_id = response.json()["id"]

    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": "student123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "student_id": student_id,
        "email": email,
        "course_id": course_id,
        "class_id": class_id,
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
