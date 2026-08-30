"""merge professional evidence with current Alembic head

Revision ID: k1f2a3b4c5d6
Revises: g8c9d0e1f2a3, j0e1f2a3b4c5
Create Date: 2026-08-30

The regulatory production-readiness branch added professional evidence from
an older Alembic head (3f273adccf42) while main had already advanced to
g8c9d0e1f2a3. After PR #57 merged, both branches became heads and Railway
could no longer execute `alembic upgrade head`.

This merge migration is intentionally schema-neutral. It preserves both
histories and restores a single canonical head without rewriting an already
merged migration.
"""
from collections.abc import Sequence

revision: str = "k1f2a3b4c5d6"
down_revision: str | Sequence[str] | None = ("g8c9d0e1f2a3", "j0e1f2a3b4c5")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
