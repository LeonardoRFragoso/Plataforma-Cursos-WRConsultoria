"""payment expiry and financial review state

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-08-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ACTIVE_PAYMENT_WHERE = (
    "enrollment_id IS NOT NULL AND "
    "status IN ('PENDENTE', 'PROCESSANDO', 'APROVADO')"
)


def upgrade() -> None:
    # PostgreSQL enum extension is additive and safe for existing rows.
    op.execute("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'EXPIRADO'")
    op.add_column(
        "payments",
        sa.Column(
            "review_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "payments",
        sa.Column("review_reason", sa.String(), nullable=True),
    )
    op.alter_column("payments", "review_required", server_default=None)

    # Fail loudly instead of silently choosing between multiple active charges.
    # Pre-launch data must be reconciled manually if this invariant was already
    # violated by legacy/direct payment creation.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT enrollment_id
                FROM payments
                WHERE enrollment_id IS NOT NULL
                  AND status IN ('PENDENTE', 'PROCESSANDO', 'APROVADO')
                GROUP BY enrollment_id
                HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Duplicate active payments exist for the same enrollment; reconcile before migrating';
            END IF;
        END $$;
        """
    )

    op.create_index(
        "uq_payment_active_attempt_per_enrollment",
        "payments",
        ["enrollment_id"],
        unique=True,
        postgresql_where=sa.text(_ACTIVE_PAYMENT_WHERE),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_payment_active_attempt_per_enrollment",
        table_name="payments",
    )
    op.drop_column("payments", "review_reason")
    op.drop_column("payments", "review_required")
    # PostgreSQL enum values cannot be removed safely in-place without
    # rebuilding the enum. Keep EXPIRADO non-destructively on downgrade.
