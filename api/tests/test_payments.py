import uuid
from datetime import date, timedelta


def _random_cpf() -> str:
    return f"{uuid.uuid4().int % 10**11:011d}"


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

    start = date.today() + timedelta(days=1)
    end = start + timedelta(days=20)
    me = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert me.status_code == 200
    admin_id = me.json()["id"]
    class_data = {
        "course_id": course_id,
        "instructor_id": admin_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "max_students": 25,
        "location": None,
        "ead_link": "https://ead.wrconsultoria.com.br/test",
        "status": "CONCLUIDA",
        "description": "Turma para teste de pagamento",
    }
    class_response = await client.post("/api/v1/classes/", json=class_data, headers=admin_headers)
    assert class_response.status_code == 201
    class_id = class_response.json()["id"]

    email = f"student_pay_{uuid.uuid4().hex[:8]}@example.com"
    cpf = _random_cpf()
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
        },
        headers=admin_headers,
    )
    assert student.status_code == 201
    student_id = student.json()["id"]

    enrollment = await client.post(
        "/api/v1/enrollments/",
        json={
            "student_id": student_id,
            "class_id": class_id,
            "price": 199.90,
            "status": "CONCLUIDA",
        },
        headers=admin_headers,
    )
    assert enrollment.status_code == 201
    return enrollment.json()["id"]


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
