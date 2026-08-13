"""
Seed data para matrículas.
Vincula alunos às turmas de exemplo.
"""

from sqlalchemy import select

from app.models.class_model import Class
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.student import Student


async def seed_enrollments(db):
    """Popula o banco com matrículas de teste."""
    print("\n📝 Populando matrículas...")

    # Buscar todos os alunos e turmas
    stmt = select(Student)
    result = await db.execute(stmt)
    students = result.scalars().all()

    stmt = select(Class)
    result = await db.execute(stmt)
    classes = result.scalars().all()

    if not students or not classes:
        print("✗ Alunos ou turmas não encontrados, pulando matrículas")
        return

    # Criar uma matrícula para cada aluno na primeira turma (concluída)
    target_statuses = [
        EnrollmentStatus.CONCLUIDA,
        EnrollmentStatus.CONFIRMADA,
        EnrollmentStatus.PENDENTE,
    ]

    for i, student in enumerate(students):
        target_class = classes[i % len(classes)]
        status = target_statuses[i % len(target_statuses)]

        stmt = select(Enrollment).where(
            Enrollment.student_id == student.id,
            Enrollment.class_id == target_class.id,
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            print(f"✓ Matrícula do aluno {student.cpf} na turma {target_class.id} já existe")
            continue

        enrollment = Enrollment(
            student_id=student.id,
            class_id=target_class.id,
            status=status,
            price=299.90,
        )
        db.add(enrollment)
        print(f"✓ Matrícula do aluno {student.cpf} na turma {target_class.id} criada ({status.value})")

    await db.commit()
    print("\n✓ Seed de matrículas concluído!")
