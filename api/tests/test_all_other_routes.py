import uuid
from datetime import timedelta

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.utils import utc_now
from app.models.payment import Payment, PaymentStatus
from app.models.user import User

COMPANY_PAYLOAD = {
    "legal_name": "Empresa Teste LTDA",
    "trade_name": "Empresa Teste",
    "cnpj": "12.345.678/0001-95",
    "rh_name": "RH Teste",
    "rh_email": "rh@empresa.com",
    "rh_phone": "(11) 99999-9999",
    "address": "Rua A, 1",
    "city": "São Paulo",
    "state": "SP",
    "zip_code": "01000-000",
}


def _class_payload(course_id, admin_id):
    today = utc_now().date()
    return {
        "course_id": str(course_id),
        "responsible_admin_id": str(admin_id),
        "start_date": today.isoformat(),
        "end_date": (today + timedelta(days=30)).isoformat(),
        "max_students": 20,
        "location": "São Paulo",
        "description": "Turma de teste",
    }


async def _admin_id(client, admin_headers):
    me = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert me.status_code == 200
    return me.json()["id"]


async def _create_course(client, admin_headers):
    payload = {
        "code": f"CUR-{uuid.uuid4().hex[:6].upper()}",
        "name": "Curso Teste",
        "category": "Segurança",
        "carga_horaria": 40,
        "modality": "PRESENCIAL",
        "price": 100.0,
        "description": "Curso de teste",
    }
    response = await client.post("/api/v1/courses/", json=payload, headers=admin_headers)
    assert response.status_code == 201
    return response.json()["id"]


async def _create_class(client, admin_headers, course_id, admin_id):
    payload = _class_payload(course_id, admin_id)
    response = await client.post("/api/v1/classes/", json=payload, headers=admin_headers)
    assert response.status_code == 201
    return response.json()["id"]


async def _create_student(client, admin_headers):
    payload = {
        "email": f"student_{uuid.uuid4().hex[:8]}@example.com",
        "full_name": "Aluno Teste",
        "password": "student123",
        "cpf": f"{uuid.uuid4().int % 10**11:011d}",
        "phone": "(11) 99999-9999",
        "company": "Empresa Teste",
        "address": "Rua do Aluno, 123",
        "city": "São Paulo",
        "state": "SP",
        "zip_code": "01000-000",
    }
    response = await client.post("/api/v1/students/", json=payload, headers=admin_headers)
    assert response.status_code == 201
    return response.json()["id"]


async def _create_enrollment(client, admin_headers, student_id, class_id):
    payload = {
        "student_id": str(student_id),
        "class_id": str(class_id),
        "price": 100.0,
    }
    response = await client.post("/api/v1/enrollments/", json=payload, headers=admin_headers)
    assert response.status_code == 201
    return response.json()["id"]


async def _create_payment(client, student_headers, enrollment_id):
    payload = {
        "enrollment_id": str(enrollment_id),
        "amount": 100.0,
        "method": "PIX",
    }
    response = await client.post("/api/v1/payments/", json=payload, headers=student_headers)
    assert response.status_code == 201
    return response.json()["id"]


class TestAuth:
    async def test_register_new_user(self, client):
        payload = {
            "email": f"user_{uuid.uuid4().hex[:8]}@example.com",
            "full_name": "Usuário Teste",
            "password": "senha123",
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 200
        assert response.json()["email"] == payload["email"]

    async def test_register_with_cpf(self, client):
        payload = {
            "email": f"user_{uuid.uuid4().hex[:8]}@example.com",
            "full_name": "Usuário Teste",
            "password": "senha123",
            "cpf": f"{uuid.uuid4().int % 10**11:011d}",
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 200
        assert response.json()["role"] == "student"

    async def test_register_duplicate_email(self, client):
        payload = {
            "email": "duplicate@example.com",
            "full_name": "Usuário Teste",
            "password": "senha123",
        }
        await client.post("/api/v1/auth/register", json=payload)
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 400

    async def test_login_with_email(self, client):
        payload = {
            "email": "login@example.com",
            "full_name": "Usuário Teste",
            "password": "senha123",
        }
        await client.post("/api/v1/auth/register", json=payload)
        response = await client.post(
            "/api/v1/auth/login",
            json={"identifier": payload["email"], "password": payload["password"]},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    async def test_login_with_cpf(self, client):
        cpf = f"{uuid.uuid4().int % 10**11:011d}"
        payload = {
            "email": f"login_cpf_{uuid.uuid4().hex[:8]}@example.com",
            "full_name": "Usuário Teste",
            "password": "senha123",
            "cpf": cpf,
        }
        await client.post("/api/v1/auth/register", json=payload)
        response = await client.post(
            "/api/v1/auth/login",
            json={"identifier": cpf, "password": payload["password"]},
        )
        assert response.status_code == 200

    async def test_login_invalid_identifier(self, client):
        response = await client.post(
            "/api/v1/auth/login",
            json={"identifier": "not-an-email-or-cpf", "password": "senha123"},
        )
        assert response.status_code == 400

    async def test_login_wrong_password(self, client):
        payload = {
            "email": "wrongpass@example.com",
            "full_name": "Usuário Teste",
            "password": "senha123",
        }
        await client.post("/api/v1/auth/register", json=payload)
        response = await client.post(
            "/api/v1/auth/login",
            json={"identifier": payload["email"], "password": "wrong"},
        )
        assert response.status_code == 401

    async def test_login_inactive_user(self, client):

        payload = {
            "email": "inactive@example.com",
            "full_name": "Usuário Inativo",
            "password": "senha123",
        }
        await client.post("/api/v1/auth/register", json=payload)
        async with AsyncSessionLocal() as session:
            user = (await session.execute(select(User).where(User.email == payload["email"]))).scalar_one()
            user.is_active = False
            await session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={"identifier": payload["email"], "password": payload["password"]},
        )
        assert response.status_code == 403

    async def test_refresh_token(self, client):
        payload = {
            "email": "refresh@example.com",
            "full_name": "Usuário Teste",
            "password": "senha123",
        }
        await client.post("/api/v1/auth/register", json=payload)
        login = await client.post(
            "/api/v1/auth/login",
            json={"identifier": payload["email"], "password": payload["password"]},
        )
        refresh_token = login.json()["refresh_token"]
        response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert response.status_code == 200
        assert "access_token" in response.json()

    async def test_refresh_invalid_token(self, client):
        response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "invalid.token.here"})
        assert response.status_code == 401

    async def test_get_me(self, client, admin_headers):
        response = await client.get("/api/v1/auth/me", headers=admin_headers)
        assert response.status_code == 200

    async def test_get_me_unauthorized(self, client):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 403


class TestCompanies:
    async def test_create_company(self, client, admin_headers):
        response = await client.post("/api/v1/companies/", json=COMPANY_PAYLOAD, headers=admin_headers)
        assert response.status_code == 201
        assert response.json()["cnpj"] == COMPANY_PAYLOAD["cnpj"].replace(".", "").replace("-", "").replace("/", "")

    async def test_list_companies(self, client, admin_headers):
        await client.post("/api/v1/companies/", json=COMPANY_PAYLOAD, headers=admin_headers)
        response = await client.get("/api/v1/companies/", headers=admin_headers)
        assert response.status_code == 200
        assert len(response.json()) > 0

    async def test_get_company(self, client, admin_headers):
        create = await client.post("/api/v1/companies/", json=COMPANY_PAYLOAD, headers=admin_headers)
        company_id = create.json()["id"]
        response = await client.get(f"/api/v1/companies/{company_id}", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["id"] == company_id

    async def test_update_company(self, client, admin_headers):
        create = await client.post("/api/v1/companies/", json=COMPANY_PAYLOAD, headers=admin_headers)
        company_id = create.json()["id"]
        response = await client.put(
            f"/api/v1/companies/{company_id}",
            json={"legal_name": "Nova Razão"},
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["legal_name"] == "Nova Razão"

    async def test_delete_company(self, client, admin_headers):
        create = await client.post("/api/v1/companies/", json=COMPANY_PAYLOAD, headers=admin_headers)
        company_id = create.json()["id"]
        response = await client.delete(f"/api/v1/companies/{company_id}", headers=admin_headers)
        assert response.status_code == 204

    async def test_company_not_found(self, client, admin_headers):
        response = await client.get(f"/api/v1/companies/{uuid.uuid4()}", headers=admin_headers)
        assert response.status_code == 404

    async def test_company_duplicate_cnpj(self, client, admin_headers):
        await client.post("/api/v1/companies/", json=COMPANY_PAYLOAD, headers=admin_headers)
        response = await client.post("/api/v1/companies/", json=COMPANY_PAYLOAD, headers=admin_headers)
        assert response.status_code == 400


class TestClasses:
    async def test_create_class(self, client, admin_headers, admin_token):
        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)
        payload = _class_payload(course_id, admin_id)
        response = await client.post("/api/v1/classes/", json=payload, headers=admin_headers)
        assert response.status_code == 201
        assert response.json()["course_id"] == course_id

    async def test_list_classes(self, client, admin_headers):
        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)
        await _create_class(client, admin_headers, course_id, admin_id)
        response = await client.get("/api/v1/classes/")
        assert response.status_code == 200
        assert len(response.json()) > 0

    async def test_get_class(self, client, admin_headers):
        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        response = await client.get(f"/api/v1/classes/{class_id}")
        assert response.status_code == 200
        assert response.json()["id"] == class_id

    async def test_update_class(self, client, admin_headers):
        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        response = await client.put(
            f"/api/v1/classes/{class_id}",
            json={"max_students": 50},
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["max_students"] == 50

    async def test_delete_class(self, client, admin_headers):
        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        response = await client.delete(f"/api/v1/classes/{class_id}", headers=admin_headers)
        assert response.status_code == 204

    async def test_class_not_found(self, client):
        response = await client.get(f"/api/v1/classes/{uuid.uuid4()}")
        assert response.status_code == 404


class TestStudents:
    async def test_create_student(self, client, admin_headers):
        student_id = await _create_student(client, admin_headers)
        response = await client.get(f"/api/v1/students/{student_id}", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["id"] == student_id

    async def test_list_students(self, client, admin_headers):
        await _create_student(client, admin_headers)
        response = await client.get("/api/v1/students/", headers=admin_headers)
        assert response.status_code == 200

    async def test_update_student(self, client, admin_headers):
        student_id = await _create_student(client, admin_headers)
        response = await client.put(
            f"/api/v1/students/{student_id}",
            json={"city": "Rio de Janeiro"},
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["city"] == "Rio de Janeiro"

    async def test_delete_student(self, client, admin_headers):
        student_id = await _create_student(client, admin_headers)
        response = await client.delete(f"/api/v1/students/{student_id}", headers=admin_headers)
        assert response.status_code == 204

    async def test_student_not_found(self, client, admin_headers):
        response = await client.get(f"/api/v1/students/{uuid.uuid4()}", headers=admin_headers)
        assert response.status_code == 404

    async def test_student_duplicate_cpf(self, client, admin_headers):
        cpf = f"{uuid.uuid4().int % 10**11:011d}"
        payload = {
            "email": f"student1_{uuid.uuid4().hex[:8]}@example.com",
            "full_name": "Aluno 1",
            "password": "student123",
            "cpf": cpf,
        }
        await client.post("/api/v1/students/", json=payload, headers=admin_headers)
        payload2 = {
            "email": f"student2_{uuid.uuid4().hex[:8]}@example.com",
            "full_name": "Aluno 2",
            "password": "student123",
            "cpf": cpf,
        }
        response = await client.post("/api/v1/students/", json=payload2, headers=admin_headers)
        assert response.status_code == 400


class TestEnrollments:
    async def test_create_enrollment(self, client, admin_headers, student_user):
        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        enrollment_id = await _create_enrollment(client, admin_headers, student_user["student_id"], class_id)
        response = await client.get(f"/api/v1/enrollments/{enrollment_id}", headers=student_user["headers"])
        assert response.status_code == 200
        assert response.json()["id"] == enrollment_id

    async def test_list_enrollments(self, client, admin_headers, student_user):
        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        await _create_enrollment(client, admin_headers, student_user["student_id"], class_id)
        response = await client.get("/api/v1/enrollments/", headers=admin_headers)
        assert response.status_code == 200
        assert len(response.json()) > 0

    async def test_update_enrollment(self, client, admin_headers, student_user):
        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        enrollment_id = await _create_enrollment(client, admin_headers, student_user["student_id"], class_id)
        response = await client.put(
            f"/api/v1/enrollments/{enrollment_id}",
            json={"status": "CONFIRMADA"},
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "CONFIRMADA"

    async def test_delete_enrollment(self, client, admin_headers, student_user):
        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        enrollment_id = await _create_enrollment(client, admin_headers, student_user["student_id"], class_id)
        response = await client.delete(f"/api/v1/enrollments/{enrollment_id}", headers=admin_headers)
        assert response.status_code == 204

    async def test_enrollment_not_found(self, client, student_user):
        response = await client.get(f"/api/v1/enrollments/{uuid.uuid4()}", headers=student_user["headers"])
        assert response.status_code == 404

    async def test_bulk_enrollments(self, client, admin_headers):
        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        student_ids = [await _create_student(client, admin_headers) for _ in range(3)]
        payload = {
            "class_id": str(class_id),
            "student_ids": [str(s) for s in student_ids],
            "price_per_student": 100.0,
        }
        response = await client.post("/api/v1/enrollments/bulk", json=payload, headers=admin_headers)
        assert response.status_code == 201
        assert len(response.json()["enrollment_ids"]) == 3

    async def test_bulk_missing_class(self, client, admin_headers):
        student_ids = [await _create_student(client, admin_headers) for _ in range(2)]
        payload = {
            "class_id": str(uuid.uuid4()),
            "student_ids": [str(s) for s in student_ids],
            "price_per_student": 100.0,
        }
        response = await client.post("/api/v1/enrollments/bulk", json=payload, headers=admin_headers)
        assert response.status_code == 404

    async def test_bulk_missing_student(self, client, admin_headers):
        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        payload = {
            "class_id": str(class_id),
            "student_ids": [str(uuid.uuid4())],
            "price_per_student": 100.0,
        }
        response = await client.post("/api/v1/enrollments/bulk", json=payload, headers=admin_headers)
        assert response.status_code == 404


class TestPayments:
    async def test_create_payment(self, client, admin_headers, student_user):
        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        enrollment_id = await _create_enrollment(client, admin_headers, student_user["student_id"], class_id)
        payment_id = await _create_payment(client, student_user["headers"], enrollment_id)
        response = await client.get(f"/api/v1/payments/{payment_id}", headers=student_user["headers"])
        assert response.status_code == 200
        assert response.json()["id"] == payment_id

    async def test_list_payments(self, client, admin_headers, student_user):
        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        enrollment_id = await _create_enrollment(client, admin_headers, student_user["student_id"], class_id)
        await _create_payment(client, student_user["headers"], enrollment_id)
        response = await client.get("/api/v1/payments/", headers=admin_headers)
        assert response.status_code == 200
        assert len(response.json()) > 0

    async def test_update_payment(self, client, admin_headers, student_user):
        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        enrollment_id = await _create_enrollment(client, admin_headers, student_user["student_id"], class_id)
        payment_id = await _create_payment(client, student_user["headers"], enrollment_id)
        response = await client.put(
            f"/api/v1/payments/{payment_id}",
            json={"status": "APROVADO"},
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "APROVADO"

    async def test_delete_payment(self, client, admin_headers, student_user):
        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        enrollment_id = await _create_enrollment(client, admin_headers, student_user["student_id"], class_id)
        payment_id = await _create_payment(client, student_user["headers"], enrollment_id)
        response = await client.delete(f"/api/v1/payments/{payment_id}", headers=admin_headers)
        assert response.status_code == 204

    async def test_payment_not_found(self, client, admin_headers):
        response = await client.get(f"/api/v1/payments/{uuid.uuid4()}", headers=admin_headers)
        assert response.status_code == 404

    async def test_mercado_pago_webhook(self, client, admin_headers, student_user):
        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        enrollment_id = await _create_enrollment(client, admin_headers, student_user["student_id"], class_id)
        payment_id = await _create_payment(client, student_user["headers"], enrollment_id)

        async with AsyncSessionLocal() as session:
            payment = await session.get(Payment, uuid.UUID(payment_id))
            payment.mercado_pago_id = "MP-123"
            payment.status = PaymentStatus.PENDENTE
            await session.commit()

        response = await client.post(
            "/api/v1/payments/webhook/mercado-pago",
            json={"id": "MP-123", "status": "approved"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_mercado_pago_webhook_unknown(self, client):
        response = await client.post(
            "/api/v1/payments/webhook/mercado-pago",
            json={"id": "MP-UNKNOWN", "status": "approved"},
        )
        assert response.status_code == 404


class TestCertificates:
    async def test_create_certificate(self, client, admin_headers, student_user):
        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        enrollment_id = await _create_enrollment(client, admin_headers, student_user["student_id"], class_id)

        response = await client.post(
            "/api/v1/certificates/",
            json={"enrollment_id": str(enrollment_id)},
            headers=admin_headers,
        )
        assert response.status_code == 201
        assert response.json()["enrollment_id"] == enrollment_id

    async def test_list_certificates(self, client, admin_headers, student_user):
        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        enrollment_id = await _create_enrollment(client, admin_headers, student_user["student_id"], class_id)
        await client.post(
            "/api/v1/certificates/",
            json={"enrollment_id": str(enrollment_id)},
            headers=admin_headers,
        )
        response = await client.get("/api/v1/certificates/", headers=admin_headers)
        assert response.status_code == 200
        assert len(response.json()) > 0

    async def test_get_certificate(self, client, admin_headers, student_user):
        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        enrollment_id = await _create_enrollment(client, admin_headers, student_user["student_id"], class_id)
        create = await client.post(
            "/api/v1/certificates/",
            json={"enrollment_id": str(enrollment_id)},
            headers=admin_headers,
        )
        cert_id = create.json()["id"]
        response = await client.get(f"/api/v1/certificates/{cert_id}", headers=student_user["headers"])
        assert response.status_code == 200
        assert response.json()["id"] == cert_id

    async def test_validate_certificate(self, client, admin_headers, student_user):
        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        enrollment_id = await _create_enrollment(client, admin_headers, student_user["student_id"], class_id)
        create = await client.post(
            "/api/v1/certificates/",
            json={"enrollment_id": str(enrollment_id)},
            headers=admin_headers,
        )
        validation_code = create.json()["validation_code"]
        response = await client.post(
            "/api/v1/certificates/validate",
            json={"validation_code": validation_code},
        )
        assert response.status_code == 200
        assert response.json()["valid"] is True

    async def test_validate_invalid_certificate(self, client):
        response = await client.post(
            "/api/v1/certificates/validate",
            json={"validation_code": "INVALID-CODE-1234"},
        )
        assert response.status_code == 200
        assert response.json()["valid"] is False

    async def test_delete_certificate(self, client, admin_headers, student_user):
        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, admin_id)
        enrollment_id = await _create_enrollment(client, admin_headers, student_user["student_id"], class_id)
        create = await client.post(
            "/api/v1/certificates/",
            json={"enrollment_id": str(enrollment_id)},
            headers=admin_headers,
        )
        cert_id = create.json()["id"]
        response = await client.delete(f"/api/v1/certificates/{cert_id}", headers=admin_headers)
        assert response.status_code == 204

    async def test_certificate_not_found(self, client, admin_headers):
        response = await client.get(f"/api/v1/certificates/{uuid.uuid4()}", headers=admin_headers)
        assert response.status_code == 404
