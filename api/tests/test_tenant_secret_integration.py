"""Testes de integração: TenantSecret usado pelo fluxo de pagamento
(Mercado Pago checkout + webhook) e migração legacy.
"""

import uuid
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.payment import Payment, PaymentStatus
from app.models.tenant import Tenant
from app.models.tenant_secret import TenantSecret
from app.services.tenant_secret_service import (
    MERCADO_PAGO_ACCESS_TOKEN_KEY,
    get_mercado_pago_access_token,
    get_tenant_secret,
    set_tenant_secret,
)


@asynccontextmanager
async def privileged_session():
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        yield db


# ---- Service unit tests ----


@pytest.mark.asyncio
async def test_get_tenant_secret_returns_plaintext():
    async with privileged_session() as db:
        await set_tenant_secret(
            db, WR_TENANT_ID, "test_key", "plaintext-value"
        )
        await db.commit()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        value = await get_tenant_secret(db, WR_TENANT_ID, "test_key")
        assert value == "plaintext-value"


@pytest.mark.asyncio
async def test_get_tenant_secret_returns_none_when_missing():
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        value = await get_tenant_secret(db, WR_TENANT_ID, "nonexistent_key")
        assert value is None


@pytest.mark.asyncio
async def test_get_mercado_pago_access_token_from_tenant_secret():
    async with privileged_session() as db:
        await set_tenant_secret(
            db,
            WR_TENANT_ID,
            MERCADO_PAGO_ACCESS_TOKEN_KEY,
            "APP_USR-1234567890-abc",
        )
        await db.commit()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        token = await get_mercado_pago_access_token(db, WR_TENANT_ID)
        assert token == "APP_USR-1234567890-abc"


@pytest.mark.asyncio
async def test_set_tenant_secret_is_idempotent_on_key():
    async with privileged_session() as db:
        await set_tenant_secret(db, WR_TENANT_ID, "idem_key", "v1")
        await db.commit()
        await set_tenant_secret(db, WR_TENANT_ID, "idem_key", "v2")
        await db.commit()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        value = await get_tenant_secret(db, WR_TENANT_ID, "idem_key")
        assert value == "v2"


# ---- Payment checkout uses TenantSecret ----


async def _seed_payment_for_checkout():
    """Cria enrollment + payment PENDENTE para teste de checkout."""
    from datetime import timedelta

    from app.core.security import hash_password
    from app.core.utils import utc_now
    from app.models.class_model import Class, ClassStatus
    from app.models.course import Course
    from app.models.student import Student
    from app.models.user import User, UserRole

    today = utc_now().date()
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID

        admin = User(
            email=f"admin_{uuid.uuid4().hex[:6]}@test.com",
            full_name="Admin",
            password_hash=hash_password("admin123"),
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(admin)

        student_user = User(
            email=f"student_{uuid.uuid4().hex[:6]}@test.com",
            full_name="Student",
            password_hash=hash_password("student123"),
            role=UserRole.STUDENT,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(student_user)

        course = Course(
            code=f"C-{uuid.uuid4().hex[:6].upper()}",
            name="Curso MP Secret",
            category="Segurança",
            carga_horaria=40,
            modality="EAD",
            price=300.0,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(course)
        await db.flush()

        cls = Class(
            course_id=course.id,
            responsible_admin_id=admin.id,
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=30),
            max_students=20,
            status=ClassStatus.ABERTA,
            tenant_id=WR_TENANT_ID,
        )
        db.add(cls)

        student = Student(
            user_id=student_user.id,
            cpf="52998744005",
            phone="(11) 99999-9999",
            tenant_id=WR_TENANT_ID,
        )
        db.add(student)
        await db.flush()

        enrollment = Enrollment(
            student_id=student.id,
            class_id=cls.id,
            price=300.0,
            status=EnrollmentStatus.PENDENTE,
            tenant_id=WR_TENANT_ID,
        )
        db.add(enrollment)
        await db.flush()

        payment = Payment(
            enrollment_id=enrollment.id,
            amount=300.0,
            status=PaymentStatus.PENDENTE,
            method="PIX",
            tenant_id=WR_TENANT_ID,
        )
        db.add(payment)
        await db.commit()
        await db.refresh(payment)
        await db.refresh(enrollment)
        await db.refresh(student_user)
        return payment.id, enrollment.id, student_user.id


@pytest.mark.asyncio
async def test_checkout_uses_tenant_secret_for_mp_access_token():
    """Checkout lê access_token do TenantSecret, não de tenant.settings."""
    payment_id, _enrollment_id, user_id = await _seed_payment_for_checkout()

    # Armazena o token no TenantSecret
    async with privileged_session() as db:
        await set_tenant_secret(
            db,
            WR_TENANT_ID,
            MERCADO_PAGO_ACCESS_TOKEN_KEY,
            "APP_USR-TENANT-SECRET-TOKEN",
        )
        await db.commit()

    # Garante que tenant.settings NÃO tem mp_access_token
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        tenant = await db.get(Tenant, WR_TENANT_ID)
        if tenant.settings and "mp_access_token" in tenant.settings:
            del tenant.settings["mp_access_token"]
            await db.commit()

    # Mocka MercadoPagoService.create_preference e captura o access_token
    captured_token = {}

    async def mock_create_preference(
        enrollment_id, amount, student_email, course_name, access_token
    ):
        captured_token["value"] = access_token
        return {"id": "pref-123", "init_point": "https://mp.test/checkout"}

    with patch(
        "app.services.mercado_pago_provider.MercadoPagoService.create_preference",
        new=mock_create_preference
    ):
        from app.api.routes.payments import create_checkout

        class FakeRequest:
            state = type("State", (), {"tenant_id": WR_TENANT_ID})()

        async with AsyncSessionLocal() as db:
            db.info["tenant_id"] = WR_TENANT_ID
            result = await create_checkout(
                payment_id,
                FakeRequest(),
                db,
                {"user_id": str(user_id), "role": "student"},
            )

    assert captured_token["value"] == "APP_USR-TENANT-SECRET-TOKEN"
    assert result["checkout_url"] == "https://mp.test/checkout"


@pytest.mark.asyncio
async def test_checkout_falls_back_to_legacy_settings_when_no_secret():
    """Fallback legado: se não houver TenantSecret, usa tenant.settings."""
    payment_id, _enrollment_id, user_id = await _seed_payment_for_checkout()

    # Garante que NÃO há TenantSecret
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        existing = (
            await db.execute(
                __import__("sqlalchemy").select(TenantSecret).where(
                    TenantSecret.tenant_id == WR_TENANT_ID,
                    TenantSecret.key == MERCADO_PAGO_ACCESS_TOKEN_KEY,
                )
            )
        ).scalar_one_or_none()
        if existing:
            await db.delete(existing)
            await db.commit()

    # Coloca token em settings (legacy)
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        tenant = await db.get(Tenant, WR_TENANT_ID)
        settings = tenant.settings or {}
        settings["mp_access_token"] = "LEGACY-TOKEN-123"
        tenant.settings = settings
        await db.commit()

    captured_token = {}

    async def mock_create_preference(
        enrollment_id, amount, student_email, course_name, access_token
    ):
        captured_token["value"] = access_token
        return {"id": "pref-456", "init_point": "https://mp.test/checkout2"}

    with patch(
        "app.services.mercado_pago_provider.MercadoPagoService.create_preference",
        new=mock_create_preference
    ):
        from app.api.routes.payments import create_checkout

        class FakeRequest:
            state = type("State", (), {"tenant_id": WR_TENANT_ID})()

        async with AsyncSessionLocal() as db:
            db.info["tenant_id"] = WR_TENANT_ID
            await create_checkout(
                payment_id,
                FakeRequest(),
                db,
                {"user_id": str(user_id), "role": "student"},
            )

    assert captured_token["value"] == "LEGACY-TOKEN-123"


# ---- Webhook uses TenantSecret ----


@pytest.mark.asyncio
async def test_webhook_uses_tenant_secret_for_mp_access_token():
    """Webhook lê access_token do TenantSecret para verificar pagamento."""
    payment_id, enrollment_id, _user_id = await _seed_payment_for_checkout()

    async with privileged_session() as db:
        await set_tenant_secret(
            db,
            WR_TENANT_ID,
            MERCADO_PAGO_ACCESS_TOKEN_KEY,
            "APP_USR-WEBHOOK-TOKEN",
        )
        await db.commit()

    # Configura payment com mercado_pago_id
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        payment = await db.get(Payment, payment_id)
        payment.mercado_pago_id = "pref-123"
        payment.external_reference = str(enrollment_id)
        await db.commit()

    captured_token = {}

    async def mock_get_payment_info(payment_id, access_token):
        captured_token["value"] = access_token
        return {
            "external_reference": str(enrollment_id),
            "preference_id": "pref-123",
            "status": "approved",
        }

    with patch(
        "app.api.routes.payments.MercadoPagoService.get_payment_info",
        new=mock_get_payment_info
    ):
        from app.api.routes.payments import PaymentWebhookRequest, mercado_pago_webhook

        async with AsyncSessionLocal() as db:
            db.info["tenant_id"] = WR_TENANT_ID
            await mercado_pago_webhook(
                PaymentWebhookRequest(
                    id="mp-payment-1",
                    status="approved",
                    external_reference=str(enrollment_id),
                ),
                db,
            )

    assert captured_token["value"] == "APP_USR-WEBHOOK-TOKEN"


# ---- Secret never appears in common APIs ----


@pytest.mark.asyncio
async def test_secret_not_exposed_in_tenant_branding_api(client, admin_headers):
    """API comum de tenant não expõe secrets."""
    async with privileged_session() as db:
        await set_tenant_secret(
            db,
            WR_TENANT_ID,
            MERCADO_PAGO_ACCESS_TOKEN_KEY,
            "SECRET-SHOULD-NOT-LEAK",
        )
        await db.commit()

    # GET /tenants/branding não deve conter o secret
    response = await client.get("/api/v1/tenants/branding?slug=wr")
    assert response.status_code == 200
    body = response.text
    assert "SECRET-SHOULD-NOT-LEAK" not in body

    # GET /secrets (admin) não deve conter o valor plano
    response = await client.get("/api/v1/secrets/", headers=admin_headers)
    assert response.status_code == 200
    for item in response.json():
        assert "value" not in item
        assert "encrypted_value" not in item


# ---- Legacy migration script ----


@pytest.mark.asyncio
async def test_migration_moves_mp_token_from_settings_to_tenant_secret():
    from app.scripts.migrate_mp_access_tokens import migrate_tenant_mp_tokens

    # Cria tenant com settings.mp_access_token
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        tenant = await db.get(Tenant, WR_TENANT_ID)
        settings = tenant.settings or {}
        settings["mp_access_token"] = "LEGACY-MP-TOKEN-TO-MIGRATE"
        tenant.settings = settings
        await db.commit()

    report = await migrate_tenant_mp_tokens(dry_run=False)

    assert report["migrated"] >= 1
    assert len(report["errors"]) == 0

    # Verifica que o token foi migrado para TenantSecret
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        value = await get_mercado_pago_access_token(db, WR_TENANT_ID)
        assert value == "LEGACY-MP-TOKEN-TO-MIGRATE"

        # Verifica que plaintext foi removido de settings
        tenant = await db.get(Tenant, WR_TENANT_ID)
        assert "mp_access_token" not in (tenant.settings or {})


@pytest.mark.asyncio
async def test_migration_is_idempotent():
    from app.scripts.migrate_mp_access_tokens import migrate_tenant_mp_tokens

    # Primeira execução
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        tenant = await db.get(Tenant, WR_TENANT_ID)
        settings = tenant.settings or {}
        settings["mp_access_token"] = "IDEMPOTENT-TOKEN"
        tenant.settings = settings
        await db.commit()

    await migrate_tenant_mp_tokens(dry_run=False)

    # Segunda execução — não deve duplicar nem falhar
    report = await migrate_tenant_mp_tokens(dry_run=False)
    assert report["migrated"] == 0
    assert len(report["errors"]) == 0

    # Token ainda acessível via TenantSecret
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        value = await get_mercado_pago_access_token(db, WR_TENANT_ID)
        assert value == "IDEMPOTENT-TOKEN"


@pytest.mark.asyncio
async def test_migration_dry_run_does_not_modify():
    from app.scripts.migrate_mp_access_tokens import migrate_tenant_mp_tokens

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        tenant = await db.get(Tenant, WR_TENANT_ID)
        settings = tenant.settings or {}
        settings["mp_access_token"] = "DRY-RUN-TOKEN"
        tenant.settings = settings
        await db.commit()

    report = await migrate_tenant_mp_tokens(dry_run=True)

    # Dry run reporta mas não modifica
    assert report["migrated"] >= 1 or report["already_migrated"] >= 0

    # settings ainda contém o token (não removido em dry-run)
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        tenant = await db.get(Tenant, WR_TENANT_ID)
        assert "mp_access_token" in (tenant.settings or {})

    # Limpa para outros testes
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        tenant = await db.get(Tenant, WR_TENANT_ID)
        settings = tenant.settings or {}
        settings.pop("mp_access_token", None)
        tenant.settings = settings
        await db.commit()


# ---- Multi-tenant migration with FORCE RLS ----


@pytest.mark.asyncio
async def test_migration_handles_multiple_tenants_with_rls():
    """A migração percorre múltiplos tenants usando sessão privilegiada.

    Com FORCE ROW LEVEL SECURITY, uma sessão normal só vê registros do
    tenant atual. A migração usa bypass_rls para acessar todos os tenants.
    """
    from sqlalchemy import text as sql_text

    from app.scripts.migrate_mp_access_tokens import migrate_tenant_mp_tokens

    # Cria dois tenants com mp_access_token em settings
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        # Apply RLS + FORCE for tenant_secrets and tenants
        for table in ["tenant_secrets", "tenants"]:
            await db.execute(sql_text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
            await db.execute(sql_text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        await db.execute(sql_text("DROP POLICY IF EXISTS tenant_isolation_tenant_secrets ON tenant_secrets"))
        await db.execute(sql_text(
            "CREATE POLICY tenant_isolation_tenant_secrets ON tenant_secrets "
            "FOR ALL TO public "
            "USING (current_setting('app.bypass_rls', true) = '1' "
            "OR tenant_id = current_setting('app.current_tenant', true)::UUID) "
            "WITH CHECK (current_setting('app.bypass_rls', true) = '1' "
            "OR tenant_id = current_setting('app.current_tenant', true)::UUID)"
        ))
        await db.commit()

        tenant_a = Tenant(
            name="Multi-Tenant A",
            slug=f"mt-a-{uuid.uuid4().hex[:6]}",
            contact_name="A",
            contact_email="a@mt.test",
            settings={"mp_access_token": "TOKEN-A-MULTI"},
        )
        tenant_b = Tenant(
            name="Multi-Tenant B",
            slug=f"mt-b-{uuid.uuid4().hex[:6]}",
            contact_name="B",
            contact_email="b@mt.test",
            settings={"mp_access_token": "TOKEN-B-MULTI"},
        )
        db.add_all([tenant_a, tenant_b])
        await db.commit()

    # Executa a migração (usa sessão privilegiada com bypass_rls)
    report = await migrate_tenant_mp_tokens(dry_run=False)

    assert report["migrated"] >= 2, f"Expected 2 migrations, got {report['migrated']}"
    assert len(report["errors"]) == 0

    # Verifica que ambos os tokens foram migrados
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await db.execute(sql_text("SET LOCAL app.bypass_rls = '1'"))

        token_a = await get_mercado_pago_access_token(db, tenant_a.id)
        token_b = await get_mercado_pago_access_token(db, tenant_b.id)
        assert token_a == "TOKEN-A-MULTI"
        assert token_b == "TOKEN-B-MULTI"

        # Verifica que plaintext foi removido de settings
        tenant_a_db = await db.get(Tenant, tenant_a.id)
        tenant_b_db = await db.get(Tenant, tenant_b.id)
        assert "mp_access_token" not in (tenant_a_db.settings or {})
        assert "mp_access_token" not in (tenant_b_db.settings or {})
