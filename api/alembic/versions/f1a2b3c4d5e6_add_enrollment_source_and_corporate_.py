"""add enrollment source and corporate enrollment batch

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-08-21 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add enrollment source enum, corporate_enrollment_batches table, and RLS."""
    # Create enrollment_source enum
    sa.Enum('INDIVIDUAL', 'CORPORATE', name='enrollmentsource').create(op.get_bind(), checkfirst=False)

    # Add source column to enrollments (default INDIVIDUAL for existing rows)
    op.add_column(
        'enrollments',
        sa.Column(
            'source',
            sa.Enum('INDIVIDUAL', 'CORPORATE', name='enrollmentsource',
                    values_callable=lambda x: [e.value for e in x]),
            nullable=False,
            server_default='INDIVIDUAL',
        ),
    )

    # Create corporate_enrollment_batches table
    op.create_table(
        'corporate_enrollment_batches',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False, index=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id'), nullable=False, index=True),
        sa.Column('class_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('classes.id'), nullable=False),
        sa.Column('enrollment_count', sa.Integer(), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_by_name', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Enable RLS on the new table
    op.execute("ALTER TABLE corporate_enrollment_batches ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE corporate_enrollment_batches FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_corporate_enrollment_batches "
        "ON corporate_enrollment_batches FOR ALL TO public "
        "USING (tenant_id = current_setting('app.current_tenant', true)::UUID)"
    )


def downgrade() -> None:
    """Remove enrollment source enum and corporate_enrollment_batches table."""
    op.execute("DROP POLICY IF EXISTS tenant_isolation_corporate_enrollment_batches ON corporate_enrollment_batches")
    op.execute("ALTER TABLE corporate_enrollment_batches NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE corporate_enrollment_batches DISABLE ROW LEVEL SECURITY")
    op.drop_table('corporate_enrollment_batches')
    op.drop_column('enrollments', 'source')
    sa.Enum(name='enrollmentsource').drop(op.get_bind(), checkfirst=False)
