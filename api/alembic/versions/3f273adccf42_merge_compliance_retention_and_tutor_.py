"""merge compliance retention and tutor knowledge rag heads

Revision ID: 3f273adccf42
Revises: i7c8d9e0f1a2, i9d0e1f2a3b4
Create Date: 2026-08-27 19:02:31.548490

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '3f273adccf42'
down_revision: str | None = ('i7c8d9e0f1a2', 'i9d0e1f2a3b4')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
