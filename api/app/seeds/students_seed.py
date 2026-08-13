"""
Seed data para alunos.
Cria registros na tabela students vinculados aos usuários com role 'student'.
"""

from app.models.user import User, UserRole
from app.models.student import Student

TEST_STUDENTS_DATA = [
    {
        "email": "student@wrcursos.com.br",
        "cpf": "11122233344",
        "phone": "(11) 99999-1111",
        "company": "WR Consultoria",
        "address": "Rua dos Testes, 100",
        "city": "São Paulo",
        "state": "SP",
        "zip_code": "01000-000",
    },
    {
        "email": "student2@wrcursos.com.br",
        "cpf": "22233344455",
        "phone": "(11) 99999-2222",
        "company": "Empresa A",
        "address": "Av. Brasil, 200",
        "city": "Rio de Janeiro",
        "state": "RJ",
        "zip_code": "20000-000",
    },
    {
        "email": "student3@wrcursos.com.br",
        "cpf": "33344455566",
        "phone": "(11) 99999-3333",
        "company": "Empresa B",
        "address": "Rua das Palmeiras, 300",
        "city": "Belo Horizonte",
        "state": "MG",
        "zip_code": "30000-000",
    },
]


async def seed_students(db):
    """Popula o banco com alunos de teste."""
    from sqlalchemy import select

    for student_data in TEST_STUDENTS_DATA:
        stmt = select(User).where(User.email == student_data["email"])
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            print(f"✗ Usuário {student_data['email']} não encontrado, pulando aluno")
            continue

        stmt = select(Student).where(Student.user_id == user.id)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            print(f"✓ Aluno {student_data['email']} já existe")
            continue

        student = Student(
            user_id=user.id,
            cpf=student_data["cpf"],
            phone=student_data["phone"],
            company=student_data["company"],
            address=student_data["address"],
            city=student_data["city"],
            state=student_data["state"],
            zip_code=student_data["zip_code"],
        )
        db.add(student)
        print(f"✓ Aluno {student_data['email']} criado")

    await db.commit()
    print("\n✓ Seed de alunos concluído!")
