"""custom domain verification lifecycle

Adiciona colunas para o lifecycle de verificação de domínio customizado:
custom_domain_status, domain_verification_token, domain_verified_at e
domain_verification_error. Domínios existentes passam a status NONE e
devem ser revalidados; o TenantResolver só considera domínios VERIFIED/
ACTIVE.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-15 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'tenants',
        sa.Column(
            'custom_domain_status',
            sa.String(),
            server_default='NONE',
            nullable=False,
        ),
    )
    op.add_column(
        'tenants',
        sa.Column('domain_verification_token', sa.String(), nullable=True),
    )
    op.add_column(
        'tenants',
        sa.Column('domain_verified_at', sa.DateTime(), nullable=True),
    )
    op.add_column(
        'tenants',
        sa.Column('domain_verification_error', sa.String(), nullable=True),
    )
    op.create_index(
        'ix_tenants_custom_domain_status',
        'tenants',
        ['custom_domain_status'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_tenants_custom_domain_status', table_name='tenants')
    op.drop_column('tenants', 'domain_verification_error')
    op.drop_column('tenants', 'domain_verified_at')
    op.drop_column('tenants', 'domain_verification_token')
    op.drop_column('tenants', 'custom_domain_status')
