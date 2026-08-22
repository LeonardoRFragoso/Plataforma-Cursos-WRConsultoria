import uuid
from datetime import timedelta

import pytest

from app.core.database import AsyncSessionLocal
from app.core.utils import utc_now
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.payment import Payment, PaymentStatus
from tests.conftest import make_valid_cpf


async def _create_test_enrollment(client, admin_headers):
    """Helper que cria curso, turma, aluno e retorna enrollment_id."""
    course = await client.post(
        "/api/v1/courses/",
        json={
            "code": f"NR-PAY-{uuid.uuid4().hex[:6].upper()}",
            "name": "Curso de Teste - Pagamento",
            "category": "Segurança",
            "carga_horaria": 20,
            "modality": "EAD",
            "tipo_curso": "FORMACAO",
            "price": 199.90,
            "description": "Curso para teste de pagamentos",
        },
        headers=admin_headers,
    )
    assert course.status_code == 201
    course_id = course.json()["id"]

    start = utc_now().date() + timedelta(days=1)
    end = start + timedelta(days=20)
    me = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert me.status_code == 200
    admin_id = me.json()["id"]
    class_data = {
        "course_id": course_id,
        "responsible_admin_id": admin_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "max_students": 25,
        "location": None,
        "ead_link": "https://ead.wrconsultoria.com.br/test",
        "status": "ABERTA",
        "description": "Turma para teste de pagamento",
    }
    class_response = await client.post("/api/v1/classes/", json=class_data, headers=admin_headers)
    assert class_response.status_code == 201
    class_id = class_response.json()["id"]

    email = f"student_pay_{uuid.uuid4().hex[:8]}@example.com"
    cpf = make_valid_cpf()
    student = await client.post(
        "/api/v1/students/",
        json={
            "email": email,
            "full_name": "Aluno Pagamento",
            "password": "student123",
            "cpf": cpf,
            "phone": "(11) 98888-7777",
            "company": "Empresa Pagamento",
            "address": "Rua do Pagamento, 456",
            "city": "São Paulo",
            "state": "SP",
            "zip_code": "02000-000",
            "class_id": class_id,
        },
        headers=admin_headers,
    )
    assert student.status_code == 201
    student_id = student.json()["id"]

    list_enrollments = await client.get("/api/v1/enrollments/", headers=admin_headers)
    assert list_enrollments.status_code == 200
    enrollment = next(
        (e for e in list_enrollments.json() if e["student_id"] == student_id and e["class_id"] == class_id),
        None,
    )
    assert enrollment is not None
    enrollment_id = enrollment["id"]

    update = await client.put(
        f"/api/v1/enrollments/{enrollment_id}",
        json={"status": "CONCLUIDA"},
        headers=admin_headers,
    )
    assert update.status_code == 200
    return enrollment_id


async def test_create_payment(client, admin_headers):
    """Deve criar um pagamento para uma matrícula existente."""
    enrollment_id = await _create_test_enrollment(client, admin_headers)

    payment_data = {
        "enrollment_id": enrollment_id,
        "amount": 199.90,
        "method": "BOLETO",
        "installments": "1x",
    }
    response = await client.post(
        "/api/v1/payments/",
        json=payment_data,
        headers=admin_headers,
    )
    assert response.status_code == 201
    assert response.json()["amount"] == 199.90
    assert response.json()["method"] == "BOLETO"
    assert response.json()["status"] == "PENDENTE"


async def test_update_payment_status(client, admin_headers):
    """Deve atualizar o status de um pagamento para APROVADO."""
    enrollment_id = await _create_test_enrollment(client, admin_headers)

    payment = await client.post(
        "/api/v1/payments/",
        json={
            "enrollment_id": enrollment_id,
            "amount": 199.90,
            "method": "PIX",
        },
        headers=admin_headers,
    )
    assert payment.status_code == 201
    payment_id = payment.json()["id"]

    update = await client.put(
        f"/api/v1/payments/{payment_id}",
        json={"status": "APROVADO"},
        headers=admin_headers,
    )
    assert update.status_code == 200
    assert update.json()["status"] == "APROVADO"


async def _seed_course_class_student(client, admin_headers, *, course_price=500.0):
    """Cria curso (preço customizável), turma ABERTA e aluno; retorna ids."""
    course = await client.post(
        "/api/v1/courses/",
        json={
            "code": f"NR-AUTH-{uuid.uuid4().hex[:6].upper()}",
            "name": "Curso Autoridade Preço",
            "category": "Segurança",
            "carga_horaria": 40,
            "modality": "EAD",
            "tipo_curso": "FORMACAO",
            "price": course_price,
            "description": "Curso para teste de autoridade de preço",
        },
        headers=admin_headers,
    )
    assert course.status_code == 201
    course_id = course.json()["id"]

    start = utc_now().date() + timedelta(days=1)
    end = start + timedelta(days=20)
    me = await client.get("/api/v1/auth/me", headers=admin_headers)
    admin_id = me.json()["id"]
    class_data = {
        "course_id": course_id,
        "responsible_admin_id": admin_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "max_students": 25,
        "location": None,
        "ead_link": "https://ead.wrconsultoria.com.br/test",
        "status": "ABERTA",
        "description": "Turma autoridade preço",
    }
    class_response = await client.post("/api/v1/classes/", json=class_data, headers=admin_headers)
    assert class_response.status_code == 201
    class_id = class_response.json()["id"]

    email = f"student_auth_{uuid.uuid4().hex[:8]}@example.com"
    cpf = make_valid_cpf()
    student = await client.post(
        "/api/v1/students/",
        json={
            "email": email,
            "full_name": "Aluno Autoridade",
            "password": "student123",
            "cpf": cpf,
            "phone": "(11) 97777-6666",
            "company": "Empresa Auth",
            "address": "Rua Auth, 1",
            "city": "São Paulo",
            "state": "SP",
            "zip_code": "03000-000",
            "class_id": class_id,
        },
        headers=admin_headers,
    )
    assert student.status_code == 201
    student_id = student.json()["id"]

    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": "student123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    student_headers = {"Authorization": f"Bearer {token}"}

    list_enrollments = await client.get("/api/v1/enrollments/", headers=admin_headers)
    enrollment = next(
        (e for e in list_enrollments.json() if e["student_id"] == student_id and e["class_id"] == class_id),
        None,
    )
    assert enrollment is not None
    return {
        "course_id": course_id,
        "class_id": class_id,
        "student_id": student_id,
        "enrollment_id": enrollment["id"],
        "student_headers": student_headers,
        "course_price": course_price,
    }


async def test_payment_amount_ignored_client_uses_server_price(client, admin_headers):
    """Course.price=500; cliente tenta criar payment amount=1 -> valor 500."""
    ctx = await _seed_course_class_student(client, admin_headers, course_price=500.0)

    response = await client.post(
        "/api/v1/payments/",
        json={
            "enrollment_id": ctx["enrollment_id"],
            "amount": 1,  # tentativa de pagar menos
            "method": "PIX",
        },
        headers=ctx["student_headers"],
    )
    assert response.status_code == 201
    body = response.json()
    # O valor informado pelo cliente é ignorado; o servidor usa Enrollment.price (500)
    assert body["amount"] == 500.0
    assert body["amount"] != 1


async def test_checkout_uses_server_price(client, admin_headers, monkeypatch):
    """Checkout deve receber o preço autoritativo (500), não o valor do cliente."""
    ctx = await _seed_course_class_student(client, admin_headers, course_price=500.0)

    payment = await client.post(
        "/api/v1/payments/",
        json={
            "enrollment_id": ctx["enrollment_id"],
            "amount": 1,
            "method": "PIX",
        },
        headers=ctx["student_headers"],
    )
    assert payment.status_code == 201
    payment_id = payment.json()["id"]
    assert payment.json()["amount"] == 500.0

    captured = {}

    class FakePreference:
        @staticmethod
        async def create_preference(*args, **kwargs):
            captured["amount"] = kwargs.get("amount", args[1] if len(args) > 1 else None)
            return {"id": "PREF-SERVER-PRICE", "init_point": "https://mp.init"}

    # Monkeypatch the MercadoPagoService in the provider module (where
    # MercadoPagoProvider imports it), not in the route module.
    monkeypatch.setattr(
        "app.services.mercado_pago_provider.MercadoPagoService",
        FakePreference,
    )

    checkout = await client.post(
        f"/api/v1/payments/{payment_id}/checkout",
        headers=ctx["student_headers"],
    )
    assert checkout.status_code == 200
    assert checkout.json()["preference_id"] == "PREF-SERVER-PRICE"
    # O checkout repassa o preço autoritativo (500), nunca o valor manipulado
    assert captured["amount"] == 500.0


@pytest.mark.asyncio
async def test_webhook_approved_does_not_release_course_with_inconsistent_payment(client, admin_headers, monkeypatch):
    """Webhook approved não libera curso quando payment.amount != enrollment.price."""
    ctx = await _seed_course_class_student(client, admin_headers, course_price=500.0)

    preference_id = f"PREF-INCONSISTENT-{uuid.uuid4().hex[:6]}"
    enrollment_id = ctx["enrollment_id"]

    # Cria um pagamento inconsistente diretamente no banco (simula fraude/bypass)
    async with AsyncSessionLocal() as db:
        from app.core.constants import WR_TENANT_ID

        inconsistent = Payment(
            tenant_id=WR_TENANT_ID,
            enrollment_id=uuid.UUID(enrollment_id),
            amount=1.0,  # inconsistente com enrollment.price (500)
            status=PaymentStatus.PROCESSANDO,
            method="PIX",
            mercado_pago_id=preference_id,
        )
        db.add(inconsistent)
        await db.commit()
        await db.refresh(inconsistent)
        payment_id = inconsistent.id

    class FakeMP:
        @staticmethod
        async def get_payment_info(*args, **kwargs):
            return {
                "id": "PAY-INCONSISTENT",
                "status": "approved",
                "external_reference": enrollment_id,
                "preference_id": preference_id,
            }

    monkeypatch.setattr(
        "app.api.routes.payments.MercadoPagoService",
        FakeMP,
    )

    webhook = await client.post(
        "/api/v1/payments/webhook/mercado-pago",
        json={"id": "PAY-INCONSISTENT", "status": "approved", "external_reference": enrollment_id},
    )
    assert webhook.status_code == 200
    assert webhook.json()["status"] == "amount_mismatch"

    # A matrícula NÃO deve ter sido confirmada
    async with AsyncSessionLocal() as db:
        enrollment = await db.get(Enrollment, uuid.UUID(enrollment_id))
        assert enrollment.status != EnrollmentStatus.CONFIRMADA
        payment = await db.get(Payment, payment_id)
        # O pagamento foi marcado como aprovado, mas o curso não foi liberado
        assert payment.status == PaymentStatus.APROVADO


@pytest.mark.asyncio
async def test_webhook_approved_releases_course_with_consistent_payment(client, admin_headers, monkeypatch):
    """Webhook approved libera curso quando payment.amount == enrollment.price."""
    ctx = await _seed_course_class_student(client, admin_headers, course_price=500.0)

    preference_id = f"PREF-CONSISTENT-{uuid.uuid4().hex[:6]}"
    enrollment_id = ctx["enrollment_id"]

    async with AsyncSessionLocal() as db:
        from app.core.constants import WR_TENANT_ID

        consistent = Payment(
            tenant_id=WR_TENANT_ID,
            enrollment_id=uuid.UUID(enrollment_id),
            amount=500.0,  # consistente
            status=PaymentStatus.PROCESSANDO,
            method="PIX",
            mercado_pago_id=preference_id,
        )
        db.add(consistent)
        await db.commit()

    class FakeMP:
        @staticmethod
        async def get_payment_info(*args, **kwargs):
            return {
                "id": "PAY-CONSISTENT",
                "status": "approved",
                "external_reference": enrollment_id,
                "preference_id": preference_id,
            }

    monkeypatch.setattr(
        "app.api.routes.payments.MercadoPagoService",
        FakeMP,
    )

    webhook = await client.post(
        "/api/v1/payments/webhook/mercado-pago",
        json={"id": "PAY-CONSISTENT", "status": "approved", "external_reference": enrollment_id},
    )
    assert webhook.status_code == 200
    assert webhook.json()["status"] == "ok"

    async with AsyncSessionLocal() as db:
        enrollment = await db.get(Enrollment, uuid.UUID(enrollment_id))
        assert enrollment.status == EnrollmentStatus.CONFIRMADA


async def test_admin_create_payment_explicit_amount(client, admin_headers):
    """Endpoint administrativo explícito permite valor manual auditável."""
    ctx = await _seed_course_class_student(client, admin_headers, course_price=500.0)

    response = await client.post(
        "/api/v1/payments/admin",
        json={
            "enrollment_id": ctx["enrollment_id"],
            "amount": 450.0,
            "method": "BOLETO",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    assert response.json()["amount"] == 450.0