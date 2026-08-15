"""tenant secret storage encrypted

Adiciona a tabela tenant_secrets para armazenamento criptografado de
secrets por tenant (gateway de pagamento, chaves de API etc.). O valor
é cifrado em Fernet na coluna encrypted_value; o par (tenant_id, key)
é único.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-15 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tenant_secrets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'tenant_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('tenants.id'),
            nullable=False,
            index=True,
        ),
        sa.Column('key', sa.String(), nullable=False, index=True),
        sa.Column('encrypted_value', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.UniqueConstraint(
            'tenant_id', 'key', name='uq_tenant_secret_key'
        ),
    )
    # RLS: tenant vê apenas seus próprios secrets; bypass para SUPER_ADMIN.
    op.execute("ALTER TABLE tenant_secrets ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_tenant_secrets ON tenant_secrets "
        "FOR ALL TO public "
        "USING (current_setting('app.bypass_rls', true) = '1' "
        "OR tenant_id = current_setting('app.current_tenant', true)::UUID) "
        "WITH CHECK (current_setting('app.bypass_rls', true) = '1' "
        "OR tenant_id = current_setting('app.current_tenant', true)::UUID)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_tenant_secrets ON tenant_secrets")
    op.execute("ALTER TABLE tenant_secrets DISABLE ROW LEVEL SECURITY")
    op.drop_table('tenant_secrets')
