"""Reconcile WR course catalog with apostilas

Data-only migration that:
1. Deactivates 31 old course codes (reciclagem variants, generic courses
   replaced by specific variants, and categories with no apostila).
2. Creates 27 new course codes (NR-11 equipment variants, NR-17 ergonomics
   variants, NR-20 level variants, NR-26 lab, NR-29 variants, NR-31 variants,
   NR-33 variants, NR-34 variants).
3. Updates 20 existing course names to match the reconciled catalog.

This migration is idempotent — running it multiple times has no additional
effect. It only touches the WR tenant (slug='wr').

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-08-26

"""
from typing import Sequence, Union

from alembic import op

revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, None] = "d7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Courses to deactivate (set is_active = false)
DEACTIVATE_CODES = [
    "NR-01-R", "NR-05-R", "NR-06-R", "NR-10-AE", "NR-10-R",
    "NR-11-F", "NR-11-R", "NR-12-R", "NR-17-F", "NR-17-R",
    "NR-18-R", "NR-20-F", "NR-20-R", "NR-22-R", "NR-23-R",
    "NR-26-R", "NR-29-F", "NR-29-R", "NR-31-R", "NR-32-R",
    "NR-33-F", "NR-33-R", "NR-34-F", "NR-34-P", "NR-35-R",
    "NR-36-R", "DP-F", "LE-F", "NEG-F", "QP-F", "SAU-F",
]

# New courses to create (only if they don't already exist)
CREATE_COURSES = [
    ("NR-11-EMP", "NR 11 - Operador de Empilhadeira", "NR 11", 16, "SEMIPRESENCIAL", "FORMACAO", 199.90),
    ("NR-11-GUI", "NR 11 - Operador de Guindauto", "NR 11", 16, "SEMIPRESENCIAL", "FORMACAO", 199.90),
    ("NR-11-MIN", "NR 11 - Operador de Mini Carregadeira", "NR 11", 16, "SEMIPRESENCIAL", "FORMACAO", 199.90),
    ("NR-11-PLA", "NR 11 - Operador de Plataforma Elevatória", "NR 11", 16, "SEMIPRESENCIAL", "FORMACAO", 199.90),
    ("NR-11-PON", "NR 11 - Operador de Ponte Rolante", "NR 11", 16, "SEMIPRESENCIAL", "FORMACAO", 199.90),
    ("NR-11-RET", "NR 11 - Operador de Retroescavadeira", "NR 11", 16, "SEMIPRESENCIAL", "FORMACAO", 199.90),
    ("NR-17-ADM", "NR 17 - Ergonomia para Atividades Administrativas", "NR 17", 8, "EAD", "FORMACAO", 149.90),
    ("NR-17-CHK", "NR 17 - Ergonomia para Operador de Checkout", "NR 17", 8, "EAD", "FORMACAO", 149.90),
    ("NR-17-TEL", "NR 17 - Ergonomia para Operador de Telemarketing/Teleatendimento", "NR 17", 8, "EAD", "FORMACAO", 149.90),
    ("NR-17-TRA", "NR 17 - Levantamento e Transporte Manual de Peso", "NR 17", 8, "EAD", "FORMACAO", 149.90),
    ("NR-20-INI", "NR 20 - Inflamáveis e Combustíveis - Inicial", "NR 20", 16, "SEMIPRESENCIAL", "FORMACAO", 199.90),
    ("NR-20-BAS", "NR 20 - Inflamáveis e Combustíveis - Básico", "NR 20", 16, "SEMIPRESENCIAL", "FORMACAO", 199.90),
    ("NR-20-INT", "NR 20 - Inflamáveis e Combustíveis - Intermediário", "NR 20", 16, "SEMIPRESENCIAL", "FORMACAO", 199.90),
    ("NR-20-AI", "NR 20 - Inflamáveis e Combustíveis - Avançado I", "NR 20", 16, "SEMIPRESENCIAL", "FORMACAO", 199.90),
    ("NR-20-AII", "NR 20 - Inflamáveis e Combustíveis - Avançado II", "NR 20", 16, "SEMIPRESENCIAL", "FORMACAO", 199.90),
    ("NR-20-ESP", "NR 20 - Inflamáveis e Combustíveis - Específico", "NR 20", 16, "SEMIPRESENCIAL", "FORMACAO", 199.90),
    ("NR-26-LAB", "NR 26 - Sinalização de Segurança para Laboratório", "NR 26", 4, "EAD", "FORMACAO", 79.90),
    ("NR-29-POR", "NR 29 - Saúde e Segurança no Trabalho Portuário", "NR 29", 8, "SEMIPRESENCIAL", "FORMACAO", 149.90),
    ("NR-29-CPATP", "NR 29 - CPATP - Comissão de Prevenção de Acidentes no Trabalho Portuário", "NR 29", 8, "SEMIPRESENCIAL", "FORMACAO", 149.90),
    ("NR-29-SIN", "NR 29 - Sinaleiro - Sinalização Manual no Trabalho Portuário", "NR 29", 8, "SEMIPRESENCIAL", "FORMACAO", 149.90),
    ("NR-31-P", "NR 31 - Saúde e Segurança no Trabalho Rural - Periódico", "NR 31", 8, "SEMIPRESENCIAL", "PERIODICO", 79.90),
    ("NR-31-AGR", "NR 31 - Saúde e Segurança com Produtos Agrotóxicos", "NR 31", 8, "SEMIPRESENCIAL", "FORMACAO", 149.90),
    ("NR-31-CIPATR", "NR 31 - CIPATR - Comissão Interna de Prevenção de Acidentes no Trabalho Rural", "NR 31", 8, "SEMIPRESENCIAL", "FORMACAO", 149.90),
    ("NR-33-AUT", "NR 33 - Espaços Confinados - Trabalhador Autorizado", "NR 33", 16, "SEMIPRESENCIAL", "FORMACAO", 249.90),
    ("NR-33-SUP", "NR 33 - Espaços Confinados - Supervisor", "NR 33", 16, "SEMIPRESENCIAL", "FORMACAO", 249.90),
    ("NR-34-ADM", "NR 34 - Segurança e Saúde no Trabalho Naval - Admissional", "NR 34", 8, "SEMIPRESENCIAL", "INICIAL", 149.90),
    ("NR-34-PER", "NR 34 - Segurança e Saúde no Trabalho Naval - Periódico", "NR 34", 8, "SEMIPRESENCIAL", "PERIODICO", 79.90),
]

# Existing courses to update (name and/or description)
UPDATE_COURSES = [
    ("NR-01-F", "NR 1 - Disposições Gerais e Gerenciamento de Riscos Ocupacionais"),
    ("NR-05-F", "NR 5 - CIPA - Comissão Interna de Prevenção de Acidentes"),
    ("NR-06-F", "NR 6 - Equipamento de Proteção Individual - EPI"),
    ("NR-10-B", "NR 10 - Segurança em Instalações e Serviços em Eletricidade - Básico"),
    ("NR-10-S", "NR 10 - Segurança no Sistema Elétrico de Potência - SEP"),
    ("NR-12-F", "NR 12 - Máquinas e Equipamentos - Geral"),
    ("NR-18-F", "NR 18 - Condições e Meio Ambiente na Indústria da Construção"),
    ("NR-22-F", "NR 22 - CIPAMIN - Segurança e Saúde na Mineração"),
    ("NR-23-F", "NR 23 - Proteção Contra Incêndios"),
    ("NR-26-F", "NR 26 - Sinalização de Segurança - Geral"),
    ("NR-31-I", "NR 31 - Saúde e Segurança no Trabalho Rural - Admissional"),
    ("NR-32-F", "NR 32 - Segurança e Saúde no Serviço de Saúde / Biossegurança"),
    ("NR-35-F", "NR 35 - Trabalho em Altura"),
    ("NR-36-F", "NR 36 - Segurança e Saúde em Frigoríficos / Abate e Processamento de Carnes"),
    ("PCA-F", "Programa de Conservação Auditiva - PCA"),
    ("PPR-F", "Programa de Proteção Respiratória - PPR"),
    ("PS-F", "Primeiros Socorros"),
    ("BV-F", "Brigada Voluntária"),
    ("DD-F", "Direção Defensiva"),
    ("GL-F", "Ginástica Laboral"),
]


def upgrade() -> None:
    # 1. Deactivate old courses
    codes_list = ", ".join(f"'{c}'" for c in DEACTIVATE_CODES)
    op.execute(
        f"""
        UPDATE courses
        SET is_active = false,
            updated_at = NOW()
        WHERE tenant_id = (SELECT id FROM tenants WHERE slug = 'wr')
          AND code IN ({codes_list})
        """
    )

    # 2. Update existing course names
    for code, name in UPDATE_COURSES:
        op.execute(
            f"""
            UPDATE courses
            SET name = '{name.replace("'", "''")}',
                is_active = true,
                updated_at = NOW()
            WHERE tenant_id = (SELECT id FROM tenants WHERE slug = 'wr')
              AND code = '{code}'
            """
        )

    # 3. Create new courses (only if they don't exist)
    for code, name, category, ch, modality, tipo, price in CREATE_COURSES:
        op.execute(
            f"""
            INSERT INTO courses (id, tenant_id, code, name, category, carga_horaria, modality, tipo_curso, price, is_active, created_at, updated_at)
            SELECT gen_random_uuid(), t.id, '{code}', '{name.replace("'", "''")}', '{category}', {ch}, '{modality}', '{tipo}', {price}, true, NOW(), NOW()
            FROM tenants t
            WHERE t.slug = 'wr'
              AND NOT EXISTS (
                SELECT 1 FROM courses c
                WHERE c.tenant_id = t.id AND c.code = '{code}'
              )
            """
        )


def downgrade() -> None:
    # Reactivate deactivated courses
    codes_list = ", ".join(f"'{c}'" for c in DEACTIVATE_CODES)
    op.execute(
        f"""
        UPDATE courses
        SET is_active = true,
            updated_at = NOW()
        WHERE tenant_id = (SELECT id FROM tenants WHERE slug = 'wr')
          AND code IN ({codes_list})
        """
    )

    # Delete created courses
    create_codes = ", ".join(f"'{c[0]}'" for c in CREATE_COURSES)
    op.execute(
        f"""
        DELETE FROM courses
        WHERE tenant_id = (SELECT id FROM tenants WHERE slug = 'wr')
          AND code IN ({create_codes})
        """
    )
