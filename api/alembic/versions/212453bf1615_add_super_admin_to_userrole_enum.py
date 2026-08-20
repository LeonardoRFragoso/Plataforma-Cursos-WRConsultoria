"""add super_admin to userrole enum

Revision ID: 212453bf1615
Revises: d4e5f6a7b8c9
Create Date: 2026-08-18 21:31:56.447206

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '212453bf1615'
down_revision: str | None = 'd4e5f6a7b8c9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'super_admin'")


def downgrade() -> None:
    pass
