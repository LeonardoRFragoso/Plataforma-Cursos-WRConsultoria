import uuid
from datetime import timedelta

from app.core.utils import utc_now
from tests.conftest import make_valid_cpf


async def test_admin_create_student_and_enroll(client, admin_headers):
    """Admin cria aluno (User + Student) e consegue matriculá-lo em uma turma."""
    # Criar curso e turma para o teste
    course = await client.post(
        "/api/v1/courses/",
        json={
            "code": f"NR-ST-{uuid.uuid4().hex[:6].upper()}",
            "name": "Curso para Teste de Aluno",
            "category": "Segurança",
            "carga_horaria": 20,
            "modality": "PRESENCIAL",
            "tipo_curso": "FORMACAO",
            "price": 150.00,
            "description": "Curso para teste de cadastro de aluno",
        },
        headers=admin_headers,
    )
    assert course.status_code == 201
    course_id = course.json()["id"]

    me = await client.get("/api/v1/auth/me", headers=admin_headers)
    admin_id = me.json()["id"]

    start = utc_now().date() + timedelta(days=1)
    end = start + timedelta(days=20)
    class_data = {
        "course_id": course_id,
        "responsible_admin_id": admin_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "max_students": 25,
        "location": "Sala de Teste",
        "ead_link": None,
        "status": "ABERTA",
        "description": "Turma para teste de aluno",
    }
    class_response = await client.post("/api/v1/classes/", json=class_data, headers=admin_headers)
    assert class_response.status_code == 201
    class_id = class_response.json()["id"]

    # Criar aluno via admin
    email = f"teststudent_{uuid.uuid4().hex[:8]}@example.com"
    cpf = make_valid_cpf()
    student_data = {
        "full_name": "Aluno Teste WR",
        "email": email,
        "cpf": cpf,
        "password": "senha123",
        "phone": "(11) 99999-9999",
        "company": "Empresa Teste",
        "address": "Rua do Aluno, 123",
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
    student = student_response.json()
    assert student["email"] == email
    assert student["full_name"] == "Aluno Teste WR"
    assert student["cpf"] == cpf
    student_id = student["id"]

    # Verificar que o aluno aparece na listagem
    list_response = await client.get("/api/v1/students/", headers=admin_headers)
    assert list_response.status_code == 200
    students = list_response.json()
    assert any(s["id"] == student_id for s in students)

    # Verificar que consegue logar com o aluno criado
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": "senha123"},
    )
    assert login.status_code == 200
    assert "access_token" in login.json()

    # Verificar que a matrícula foi criada automaticamente
    enrollment_response = await client.get("/api/v1/enrollments/", headers=admin_headers)
    assert enrollment_response.status_code == 200
    enrollments = enrollment_response.json()
    assert any(e["student_id"] == student_id and e["class_id"] == class_id for e in enrollments)