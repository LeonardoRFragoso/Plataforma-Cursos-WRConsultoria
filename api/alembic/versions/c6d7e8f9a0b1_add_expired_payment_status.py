"""add expired payment status

Revision ID: c6d7e8f9a0b1
Revises: f2a3b4c5d6e7
Create Date: 2026-08-25

"""
from typing import Sequence, Union

from alembic import op


revision: str = "c6d7e8f9a0b1"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'EXPIRADO'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely in-place without
    # rebuilding the type. Keep downgrade non-destructive, matching the
    # existing enum-extension migration strategy in this project.
    pass
