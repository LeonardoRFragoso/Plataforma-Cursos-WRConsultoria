"""
Seed data para usuários de teste.
"""

from app.core.security import hash_password
from app.models.user import User, UserRole

TEST_USERS = [
    {
        "email": "admin@wrcursos.com.br",
        "cpf": "12345678901",
        "full_name": "Administrador WR",
        "password": "admin123",
        "role": UserRole.ADMIN,
    },
    {
        "email": "instructor@wrcursos.com.br",
        "cpf": "98765432109",
        "full_name": "Instrutor WR",
        "password": "instructor123",
        "role": UserRole.INSTRUCTOR,
    },
    {
        "email": "student@wrcursos.com.br",
        "cpf": "11122233344",
        "full_name": "Aluno WR",
        "password": "student123",
        "role": UserRole.STUDENT,
    },
]

async def seed_users(db):
    """Popula o banco com usuários de teste."""
    for user_data in TEST_USERS:
        # Verificar se usuário já existe
        from sqlalchemy import select
        stmt = select(User).where(User.email == user_data["email"])
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            print(f"✓ Usuário {user_data['email']} já existe")
            continue
        
        # Criar novo usuário
        user = User(
            email=user_data["email"],
            cpf=user_data["cpf"],
            full_name=user_data["full_name"],
            password_hash=hash_password(user_data["password"]),
            role=user_data["role"],
        )
        db.add(user)
        print(f"✓ Usuário {user_data['email']} criado")
    
    await db.commit()
    print("\n✓ Seed de usuários concluído!")
