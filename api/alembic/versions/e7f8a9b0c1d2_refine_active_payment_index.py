"""refine active payment attempt uniqueness

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-08-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "d6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PAYABLE_ATTEMPT_WHERE = (
    "enrollment_id IS NOT NULL AND "
    "status IN ('PENDENTE', 'PROCESSANDO')"
)

_PREVIOUS_ACTIVE_WHERE = (
    "enrollment_id IS NOT NULL AND "
    "status IN ('PENDENTE', 'PROCESSANDO', 'APROVADO')"
)


def upgrade() -> None:
    # APROVADO is terminal financial history, not a simultaneously payable
    # attempt. Application-level purchase rules still prevent a second charge
    # when an approved payment exists for a pending/acquired enrollment.
    op.drop_index(
        "uq_payment_active_attempt_per_enrollment",
        table_name="payments",
    )
    op.create_index(
        "uq_payment_active_attempt_per_enrollment",
        "payments",
        ["enrollment_id"],
        unique=True,
        postgresql_where=sa.text(_PAYABLE_ATTEMPT_WHERE),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_payment_active_attempt_per_enrollment",
        table_name="payments",
    )
    op.create_index(
        "uq_payment_active_attempt_per_enrollment",
        "payments",
        ["enrollment_id"],
        unique=True,
        postgresql_where=sa.text(_PREVIOUS_ACTIVE_WHERE),
    )
