import uuid
from datetime import timedelta

from app.core.utils import utc_now


def _random_cpf() -> str:
    return f"{uuid.uuid4().int % 10**11:011d}"


def _random_email() -> str:
    return f"student_{uuid.uuid4().hex[:8]}@example.com"


async def test_full_enrollment_payment_certificate_flow(client, admin_headers):
    """Fluxo core: curso -> turma -> aluno -> matrícula -> pagamento -> certificado -> validação."""
    # 1. Criar curso
    course_data = {
        "code": f"NR-TEST-{uuid.uuid4().hex[:6].upper()}",
        "name": "Curso de Teste - Fluxo Completo",
        "category": "Segurança",
        "carga_horaria": 40,
        "modality": "PRESENCIAL",
        "tipo_curso": "FORMACAO",
        "price": 299.90,
        "description": "Curso criado para teste do fluxo",
    }
    response = await client.post("/api/v1/courses/", json=course_data, headers=admin_headers)
    assert response.status_code == 201
    course_id = response.json()["id"]

    # 2. Obter ID do admin para instrutor
    me = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert me.status_code == 200
    admin_id = me.json()["id"]

    # 3. Criar turma
    start = utc_now().date() + timedelta(days=1)
    end = start + timedelta(days=30)
    class_data = {
        "course_id": course_id,
        "responsible_admin_id": admin_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "max_students": 30,
        "location": "Sala de Testes",
        "ead_link": None,
        "status": "ABERTA",
        "description": "Turma de teste",
    }
    class_response = await client.post("/api/v1/classes/", json=class_data, headers=admin_headers)
    assert class_response.status_code == 201
    class_id = class_response.json()["id"]

    # 4. Criar aluno
    email = _random_email()
    cpf = _random_cpf()
    student_data = {
        "email": email,
        "full_name": "Aluno Teste",
        "password": "student123",
        "cpf": cpf,
        "phone": "(11) 99999-9999",
        "company": "Empresa Teste",
        "address": "Rua do Fluxo, 123",
        "city": "São Paulo",
        "state": "SP",
        "zip_code": "01000-000",
        "class_id": class_id,
    }
    student_response = await client.post(
        "/api/v1/students/",
        json=student_data,
        headers=admin_headers,
    )
    assert student_response.status_code == 201
    student_id = student_response.json()["id"]

    # 6. Buscar matrícula automática e atualizar para concluída
    list_enrollments = await client.get("/api/v1/enrollments/", headers=admin_headers)
    assert list_enrollments.status_code == 200
    enrollment = next(
        (e for e in list_enrollments.json() if e["student_id"] == student_id and e["class_id"] == class_id),
        None,
    )
    assert enrollment is not None
    enrollment_id = enrollment["id"]

    update_response = await client.put(
        f"/api/v1/enrollments/{enrollment_id}",
        json={"status": "CONCLUIDA"},
        headers=admin_headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "CONCLUIDA"

    # 7. Criar pagamento
    payment_data = {
        "enrollment_id": enrollment_id,
        "amount": 299.90,
        "method": "PIX",
    }
    payment_response = await client.post(
        "/api/v1/payments/",
        json=payment_data,
        headers=admin_headers,
    )
    assert payment_response.status_code == 201
    assert payment_response.json()["status"] == "PENDENTE"

    # 8. Gerar certificado
    certificate_response = await client.post(
        "/api/v1/certificates/",
        json={"enrollment_id": enrollment_id},
        headers=admin_headers,
    )
    assert certificate_response.status_code == 201
    certificate = certificate_response.json()
    assert certificate["certificate_number"].startswith("CERT-")
    assert certificate["validation_code"]

    # 9. Validar certificado publicamente
    validation = await client.post(
        "/api/v1/certificates/validate",
        json={"validation_code": certificate["validation_code"]},
    )
    assert validation.status_code == 200
    assert validation.json()["valid"] is True
    assert validation.json()["certificate_number"] == certificate["certificate_number"]