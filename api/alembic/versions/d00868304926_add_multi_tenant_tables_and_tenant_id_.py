"""add multi-tenant tables and tenant_id columns

Revision ID: d00868304926
Revises: 844b5516b310
Create Date: 2026-08-14 23:51:38.640059

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd00868304926'
down_revision: Union[str, None] = '844b5516b310'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


WR_TENANT_ID = '11111111-1111-1111-1111-111111111111'

TENANT_DOMAIN_TABLES = [
    'attendances',
    'certificates',
    'classes',
    'companies',
    'courses',
    'enrollments',
    'lesson_materials',
    'lesson_progress',
    'lessons',
    'payments',
    'students',
    'users',
]


def upgrade() -> None:
    # 1. Criar tabelas globais
    op.create_table(
        'tenants',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('legal_name', sa.String(), nullable=True),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('cnpj', sa.String(), nullable=True),
        sa.Column('custom_domain', sa.String(), nullable=True),
        sa.Column('logo_url', sa.String(), nullable=True),
        sa.Column('logo_white_url', sa.String(), nullable=True),
        sa.Column('favicon_url', sa.String(), nullable=True),
        sa.Column('primary_color', sa.String(), nullable=True),
        sa.Column('secondary_color', sa.String(), nullable=True),
        sa.Column('accent_color', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='ACTIVE'),
        sa.Column('plan', sa.String(), nullable=True),
        sa.Column('contact_name', sa.String(), nullable=False),
        sa.Column('contact_email', sa.String(), nullable=False),
        sa.Column('contact_phone', sa.String(), nullable=True),
        sa.Column('settings', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tenants_custom_domain'), 'tenants', ['custom_domain'], unique=True)
    op.create_index(op.f('ix_tenants_slug'), 'tenants', ['slug'], unique=True)

    op.create_table(
        'partner_leads',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=True),
        sa.Column('company_name', sa.String(), nullable=False),
        sa.Column('cnpj', sa.String(), nullable=True),
        sa.Column('contact_name', sa.String(), nullable=False),
        sa.Column('contact_email', sa.String(), nullable=False),
        sa.Column('contact_phone', sa.String(), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='NEW'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('approved_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    # 3. Criar tenant master da WR
    op.execute(
        f"INSERT INTO tenants (id, name, slug, status, contact_name, contact_email, created_at, updated_at) "
        f"VALUES ('{WR_TENANT_ID}', 'WR Consultoria e Soluções em QSMS', 'wr', 'ACTIVE', 'Admin WR', "
        f"'admin@wrconsultoriaesolucoes.com.br', now(), now())"
    )

    # 4. Adicionar tenant_id de forma segura (nullable, backfill, not null, FK, índice)
    op.add_column('attendances', sa.Column('tenant_id', sa.UUID(), nullable=True))
    op.add_column('certificates', sa.Column('tenant_id', sa.UUID(), nullable=True))
    op.add_column('classes', sa.Column('tenant_id', sa.UUID(), nullable=True))
    op.add_column('companies', sa.Column('tenant_id', sa.UUID(), nullable=True))
    op.add_column('courses', sa.Column('tenant_id', sa.UUID(), nullable=True))
    op.add_column('enrollments', sa.Column('tenant_id', sa.UUID(), nullable=True))
    op.add_column('lesson_materials', sa.Column('tenant_id', sa.UUID(), nullable=True))
    op.add_column('lesson_progress', sa.Column('tenant_id', sa.UUID(), nullable=True))
    op.add_column('lessons', sa.Column('tenant_id', sa.UUID(), nullable=True))
    op.add_column('payments', sa.Column('tenant_id', sa.UUID(), nullable=True))
    op.add_column('students', sa.Column('tenant_id', sa.UUID(), nullable=True))
    op.add_column('users', sa.Column('tenant_id', sa.UUID(), nullable=True))

    for table in TENANT_DOMAIN_TABLES:
        op.execute(f"UPDATE {table} SET tenant_id = '{WR_TENANT_ID}' WHERE tenant_id IS NULL")
        op.alter_column(table, 'tenant_id', nullable=False)
        op.create_index(op.f(f'ix_{table}_tenant_id'), table, ['tenant_id'], unique=False)
        op.create_foreign_key(None, table, 'tenants', ['tenant_id'], ['id'])

    # 4. Ajustar índices/unique por tenant
    op.drop_index('ix_companies_cnpj', table_name='companies')
    op.create_index(op.f('ix_companies_cnpj'), 'companies', ['cnpj'], unique=False)
    op.create_unique_constraint('uq_company_tenant_cnpj', 'companies', ['tenant_id', 'cnpj'])

    op.drop_index('ix_courses_code', table_name='courses')
    op.create_index(op.f('ix_courses_code'), 'courses', ['code'], unique=False)
    op.create_unique_constraint('uq_course_tenant_code', 'courses', ['tenant_id', 'code'])

    op.drop_constraint('uq_enrollment_student_class', 'enrollments', type_='unique')
    op.create_unique_constraint('uq_enrollment_tenant_student_class', 'enrollments', ['tenant_id', 'student_id', 'class_id'])

    op.drop_index('ix_students_cpf', table_name='students')
    op.create_index(op.f('ix_students_cpf'), 'students', ['cpf'], unique=False)
    op.create_unique_constraint('uq_student_tenant_cpf', 'students', ['tenant_id', 'cpf'])
    op.create_unique_constraint('uq_student_user_id', 'students', ['user_id'])

    op.drop_index('ix_users_cpf', table_name='users')
    op.create_index(op.f('ix_users_cpf'), 'users', ['cpf'], unique=False)
    op.drop_index('ix_users_email', table_name='users')
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=False)
    op.create_unique_constraint('uq_user_tenant_cpf', 'users', ['tenant_id', 'cpf'], deferrable='True', initially='DEFERRED')
    op.create_unique_constraint('uq_user_tenant_email', 'users', ['tenant_id', 'email'])


def _drop_fk(table: str) -> None:
    """Remove a foreign key de tenant_id de uma tabela de domínio."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    fks = inspector.get_foreign_keys(table)
    for fk in fks:
        if "tenant_id" in fk.get("constrained_columns", []):
            op.drop_constraint(fk["name"], table, type_="foreignkey")
            return


def _restore_unique_index(table: str, name: str, columns: list) -> None:
    """Recria índice unique removido no upgrade."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = {i["name"] for i in inspector.get_indexes(table)}
    if name not in existing:
        op.create_index(name, table, columns, unique=True)


def downgrade() -> None:
    # 1. Restaurar constraints/índices originais
    op.drop_constraint('uq_user_tenant_email', 'users', type_='unique')
    op.drop_constraint('uq_user_tenant_cpf', 'users', type_='unique')
    _restore_unique_index('users', 'ix_users_email', ['email'])
    _restore_unique_index('users', 'ix_users_cpf', ['cpf'])

    op.drop_constraint('uq_student_tenant_cpf', 'students', type_='unique')
    op.drop_constraint('uq_student_user_id', 'students', type_='unique')
    _restore_unique_index('students', 'ix_students_cpf', ['cpf'])

    op.drop_constraint('uq_enrollment_tenant_student_class', 'enrollments', type_='unique')
    op.create_unique_constraint('uq_enrollment_student_class', 'enrollments', ['student_id', 'class_id'])

    op.drop_constraint('uq_course_tenant_code', 'courses', type_='unique')
    _restore_unique_index('courses', 'ix_courses_code', ['code'])

    op.drop_constraint('uq_company_tenant_cnpj', 'companies', type_='unique')
    _restore_unique_index('companies', 'ix_companies_cnpj', ['cnpj'])

    # 2. Remover colunas tenant_id e índices
    for table in TENANT_DOMAIN_TABLES:
        _drop_fk(table)
        idx_name = f'ix_{table}_tenant_id'
        try:
            op.drop_index(op.f(idx_name), table_name=table)
        except Exception:
            pass
        op.drop_column(table, 'tenant_id')

    # 3. Remover tabelas globais
    op.drop_table('partner_leads')
    op.drop_index(op.f('ix_tenants_slug'), table_name='tenants')
    op.drop_index(op.f('ix_tenants_custom_domain'), table_name='tenants')
    op.drop_table('tenants')

    # (sem tipos ENUM nomeados para recriar no downgrade)
