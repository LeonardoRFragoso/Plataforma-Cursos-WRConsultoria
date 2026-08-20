"""Remove instructor role

Revision ID: 21ff61f1fa3f
Revises: 4b2de4321703
Create Date: 2026-08-13 09:21:18.435371

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '21ff61f1fa3f'
down_revision: str | None = '4b2de4321703'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Normalizar labels do enum para minúsculas (como no UserRole Python)
    op.execute("ALTER TYPE userrole RENAME VALUE 'ADMIN' TO 'admin'")
    op.execute("ALTER TYPE userrole RENAME VALUE 'INSTRUCTOR' TO 'instructor'")
    op.execute("ALTER TYPE userrole RENAME VALUE 'STUDENT' TO 'student'")

    # Converter usuários com role 'instructor' para 'admin'
    op.execute("UPDATE users SET role = 'admin' WHERE role::text = 'instructor'")


def downgrade() -> None:
    pass
