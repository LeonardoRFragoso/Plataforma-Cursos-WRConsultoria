#!/usr/bin/env python3
"""
Script para popular o banco de dados com dados de teste.
Uso: python seed_db.py
"""

import asyncio

from app.core.database import get_db
from app.models.course import Course, CourseModality, CourseType
from app.seeds.courses_seed import COURSES_DATA
from app.seeds.users_seed import seed_users


async def main():
    print("🌱 Iniciando seed do banco de dados...\n")
    print("⚠️  Execute 'alembic upgrade head' antes do seed para garantir as tabelas.\n")
    
    # Seed de usuários
    print("📝 Populando usuários...")
    async for db in get_db():
        await seed_users(db)
        break
    
    # Seed de cursos
    print("\n📚 Populando cursos...")
    async for db in get_db():
        from sqlalchemy import select
        
        for course_data in COURSES_DATA:
            # Verificar se curso já existe
            stmt = select(Course).where(Course.code == course_data["code"])
            result = await db.execute(stmt)
            if result.scalar_one_or_none():
                print(f"✓ Curso {course_data['code']} já existe")
                continue
            
            # Criar novo curso
            course = Course(
                code=course_data["code"],
                name=course_data["name"],
                category=course_data["category"],
                carga_horaria=course_data["carga_horaria"],
                modality=CourseModality(course_data["modality"]),
                tipo_curso=CourseType(course_data["tipo_curso"]),
                price=course_data["price"],
            )
            db.add(course)
            print(f"✓ Curso {course_data['code']} criado")
        
        await db.commit()
        break
    
    # Seed de alunos
    print("\n👥 Populando alunos...")
    from app.seeds.students_seed import seed_students
    async for db in get_db():
        await seed_students(db)
        break
    
    # Seed de turmas
    print("\n📅 Populando turmas...")
    from app.seeds.classes_seed import seed_classes
    async for db in get_db():
        await seed_classes(db)
        break
    
    # Seed de matrículas
    print("\n📝 Populando matrículas...")
    from app.seeds.enrollments_seed import seed_enrollments
    async for db in get_db():
        await seed_enrollments(db)
        break
    
    # Seed de pagamentos
    print("\n💳 Populando pagamentos...")
    from app.seeds.payments_seed import seed_payments
    async for db in get_db():
        await seed_payments(db)
        break
    
    # Seed de certificados
    print("\n🏆 Populando certificados...")
    from app.seeds.certificates_seed import seed_certificates
    async for db in get_db():
        await seed_certificates(db)
        break
    
    print("\n✓ Seed concluído com sucesso!")
    print("\n📋 Usuários de teste:")
    print("  Admin:      admin@wrcursos.com.br / admin123")
    print("  Aluno:      student@wrcursos.com.br / student123")
    print("  Aluno 2:    student2@wrcursos.com.br / student123")
    print("  Aluno 3:    student3@wrcursos.com.br / student123")
    print("\n💡 Você também pode logar com CPF:")
    print("  Admin:      12345678901 / admin123")
    print("  Aluno:      11122233344 / student123")

if __name__ == "__main__":
    asyncio.run(main())
