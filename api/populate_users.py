#!/usr/bin/env python3
"""
Script para popular o banco com usuários de teste.
Uso: python3 populate_users.py
"""

import asyncio
import sys
from sqlalchemy import select
from app.core.database import AsyncSession, engine
from app.models.user import User, UserRole
from app.core.security import hash_password

TEST_USERS = [
    {
        "email": "admin@wrcursos.com.br",
        "cpf": "12345678901",
        "full_name": "Administrador WR",
        "password": "admin123",
        "role": UserRole.ADMIN,
    },
    {
        "email": "student@wrcursos.com.br",
        "cpf": "11122233344",
        "full_name": "Aluno WR",
        "password": "student123",
        "role": UserRole.STUDENT,
    },
]

async def main():
    print("🌱 Populando banco com usuários de teste...\n")
    
    # Adicionar usuários
    async with AsyncSession(engine) as session:
        for user_data in TEST_USERS:
            # Verificar se usuário já existe
            stmt = select(User).where(User.email == user_data["email"])
            result = await session.execute(stmt)
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
            session.add(user)
            print(f"✓ Usuário {user_data['email']} criado")
        
        await session.commit()
    
    print("\n✓ Usuários populados com sucesso!")
    print("\n📋 Usuários de teste:")
    print("  Admin:      admin@wrcursos.com.br / admin123")
    print("  Aluno:      student@wrcursos.com.br / student123")
    print("\n💡 Você também pode logar com CPF:")
    print("  Admin:      12345678901 / admin123")
    print("  Aluno:      11122233344 / student123")

if __name__ == "__main__":
    asyncio.run(main())
