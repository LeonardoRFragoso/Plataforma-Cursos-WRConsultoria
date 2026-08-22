"""add payment provider abstraction and asaas support

Adds:
- payments.provider, payments.provider_payment_id, payments.checkout_url
- payment_customers table (tenant-scoped provider customer mapping)
- payment_webhook_events table (idempotent webhook event log)
- paymentmethod enum gains UNDEFINED value
- paymentprovider enum (MERCADO_PAGO, ASAAS)

Backward compatible: existing rows default to MERCADO_PAGO and the
legacy mercado_pago_id column is preserved.

Revision ID: a1b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-08-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a1b3c4d5e6f7'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add provider abstraction columns and tables."""
    bind = op.get_bind()

    # 1. Add UNDEFINED to paymentmethod enum (checkfirst for safety).
    op.execute(
        "DO $$ BEGIN "
        "ALTER TYPE paymentmethod ADD VALUE IF NOT EXISTS 'UNDEFINED'; "
        "EXCEPTION WHEN OTHERS THEN NULL; END $$"
    )

    # 2. Create paymentprovider enum (checkfirst doesn't work reliably
    # with asyncpg, so use DO $$ block).
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE paymentprovider AS ENUM ('MERCADO_PAGO', 'ASAAS'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )

    # 3. Add provider columns to payments.
    # Use postgresql.ENUM with create_type=False to avoid duplicate creation.
    provider_enum = postgresql.ENUM(
        'MERCADO_PAGO', 'ASAAS', name='paymentprovider', create_type=False
    )
    op.add_column(
        'payments',
        sa.Column(
            'provider',
            provider_enum,
            nullable=False,
            server_default='MERCADO_PAGO',
        ),
    )
    op.add_column(
        'payments',
        sa.Column('provider_payment_id', sa.String(), nullable=True),
    )
    op.add_column(
        'payments',
        sa.Column('checkout_url', sa.String(), nullable=True),
    )
    op.create_index(
        'ix_payments_provider_payment_id',
        'payments',
        ['provider_payment_id'],
    )

    # 4. Backfill provider_payment_id from mercado_pago_id for legacy rows.
    op.execute(
        "UPDATE payments SET provider_payment_id = mercado_pago_id "
        "WHERE provider_payment_id IS NULL AND mercado_pago_id IS NOT NULL"
    )

    # 5. Create payment_customers table.
    op.create_table(
        'payment_customers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'tenant_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('tenants.id'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'provider',
            postgresql.ENUM(
                'MERCADO_PAGO', 'ASAAS', name='paymentprovider', create_type=False
            ),
            nullable=False,
            server_default='MERCADO_PAGO',
        ),
        sa.Column('provider_customer_id', sa.String(), nullable=False),
        sa.Column(
            'student_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('students.id'),
            nullable=True,
        ),
        sa.Column(
            'company_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('companies.id'),
            nullable=True,
        ),
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
            'tenant_id', 'student_id', 'provider',
            name='uq_payment_customer_student_provider',
        ),
        sa.UniqueConstraint(
            'tenant_id', 'company_id', 'provider',
            name='uq_payment_customer_company_provider',
        ),
    )

    # 6. Create payment_webhook_events table.
    op.create_table(
        'payment_webhook_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'tenant_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('tenants.id'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'provider',
            postgresql.ENUM(
                'MERCADO_PAGO', 'ASAAS', name='paymentprovider', create_type=False
            ),
            nullable=False,
            server_default='ASAAS',
        ),
        sa.Column('provider_event_id', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=True),
        sa.Column('provider_payment_id', sa.String(), nullable=True),
        sa.Column('payload', sa.String(), nullable=True),
        sa.Column(
            'processed_at',
            sa.DateTime(),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('result', sa.String(), nullable=True),
        sa.UniqueConstraint(
            'tenant_id', 'provider', 'provider_event_id',
            name='uq_payment_webhook_event_provider',
        ),
    )

    # 7. RLS on new tables.
    op.execute("ALTER TABLE payment_customers ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_payment_customers "
        "ON payment_customers FOR ALL TO public "
        "USING (current_setting('app.bypass_rls', true) = '1' "
        "OR tenant_id = current_setting('app.current_tenant', true)::UUID) "
        "WITH CHECK (current_setting('app.bypass_rls', true) = '1' "
        "OR tenant_id = current_setting('app.current_tenant', true)::UUID)"
    )
    op.execute("ALTER TABLE payment_webhook_events ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_payment_webhook_events "
        "ON payment_webhook_events FOR ALL TO public "
        "USING (current_setting('app.bypass_rls', true) = '1' "
        "OR tenant_id = current_setting('app.current_tenant', true)::UUID) "
        "WITH CHECK (current_setting('app.bypass_rls', true) = '1' "
        "OR tenant_id = current_setting('app.current_tenant', true)::UUID)"
    )


def downgrade() -> None:
    """Remove provider abstraction columns and tables."""
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_payment_webhook_events "
        "ON payment_webhook_events"
    )
    op.execute("ALTER TABLE payment_webhook_events DISABLE ROW LEVEL SECURITY")
    op.drop_table('payment_webhook_events')

    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_payment_customers "
        "ON payment_customers"
    )
    op.execute("ALTER TABLE payment_customers DISABLE ROW LEVEL SECURITY")
    op.drop_table('payment_customers')

    op.drop_index('ix_payments_provider_payment_id', table_name='payments')
    op.drop_column('payments', 'checkout_url')
    op.drop_column('payments', 'provider_payment_id')
    op.drop_column('payments', 'provider')

    op.execute("DROP TYPE IF EXISTS paymentprovider")
    # NOTE: cannot remove a single value from a postgres enum; leave
    # UNDEFINED in paymentmethod to avoid cascading type rebuilds.
