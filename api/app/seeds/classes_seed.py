"""
Seed data para turmas.
Cria turmas de exemplo vinculadas aos cursos e instrutor.
"""

from datetime import date, timedelta

from sqlalchemy import select

from app.models.class_model import Class, ClassStatus
from app.models.course import Course
from app.models.user import User


async def seed_classes(db):
    """Popula o banco com turmas de teste."""
    print("\n📅 Populando turmas...")

    # Buscar admin como responsável pelas turmas
    stmt = select(User).where(User.email == "admin@wrcursos.com.br")
    result = await db.execute(stmt)
    admin = result.scalar_one_or_none()
    if not admin:
        print("✗ Admin não encontrado, pulando turmas")
        return

    # Dados das turmas (código do curso -> dados)
    classes_data = [
        {
            "course_code": "NR-10-B",
            "start_date": date.today() + timedelta(days=7),
            "end_date": date.today() + timedelta(days=37),
            "max_students": 30,
            "location": "Sala 101 - WR",
            "ead_link": None,
            "status": ClassStatus.ABERTA,
            "description": "Turma presencial de NR 10 Básico",
        },
        {
            "course_code": "NR-17-F",
            "start_date": date.today() + timedelta(days=14),
            "end_date": date.today() + timedelta(days=21),
            "max_students": 25,
            "location": None,
            "ead_link": "https://ead.wrconsultoria.com.br/nr-17",
            "status": ClassStatus.EM_ANDAMENTO,
            "description": "Turma EAD de NR 17 Ergonomia",
        },
        {
            "course_code": "NR-05-F",
            "start_date": date.today() - timedelta(days=60),
            "end_date": date.today() - timedelta(days=30),
            "max_students": 20,
            "location": "Sala 102 - WR",
            "ead_link": None,
            "status": ClassStatus.CONCLUIDA,
            "description": "Turma concluída de NR 5 CIPA",
        },
    ]

    for class_data in classes_data:
        stmt = select(Course).where(Course.code == class_data["course_code"])
        result = await db.execute(stmt)
        course = result.scalar_one_or_none()

        if not course:
            print(f"✗ Curso {class_data['course_code']} não encontrado, pulando turma")
            continue

        # Verificar se turma já existe para este curso + datas
        stmt = select(Class).where(
            Class.course_id == course.id,
            Class.start_date == class_data["start_date"],
            Class.end_date == class_data["end_date"],
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            print(f"✓ Turma {course.name} já existe")
            continue

        new_class = Class(
            course_id=course.id,
            instructor_id=admin.id,
            start_date=class_data["start_date"],
            end_date=class_data["end_date"],
            max_students=class_data["max_students"],
            location=class_data["location"],
            ead_link=class_data["ead_link"],
            status=class_data["status"],
            description=class_data["description"],
        )
        db.add(new_class)
        print(f"✓ Turma {course.name} ({class_data['status'].value}) criada")

    await db.commit()
    print("\n✓ Seed de turmas concluído!")
