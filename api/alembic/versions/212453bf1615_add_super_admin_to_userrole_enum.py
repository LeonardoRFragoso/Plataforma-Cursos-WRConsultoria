"""add super_admin to userrole enum

Revision ID: 212453bf1615
Revises: d4e5f6a7b8c9
Create Date: 2026-08-18 21:31:56.447206

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '212453bf1615'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'super_admin'")


def downgrade() -> None:
    pass
