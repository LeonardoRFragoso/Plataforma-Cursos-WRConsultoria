"""WR tenant premium branding color

Update the WR tenant primary_color from the legacy blue (#0056b3) to the
approved WR premium green (#047F37). This is a data-only migration — no
schema changes. The color is tenant-based (not role-based): all WR users
(admin, student, etc.) receive the same brand identity.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-08-26

"""
from typing import Sequence, Union

from alembic import op


revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE tenants
        SET primary_color = '#047F37',
            secondary_color = '#17324D',
            accent_color = '#F59E0B'
        WHERE slug = 'wr'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE tenants
        SET primary_color = '#0056b3',
            secondary_color = '#1a1a1a',
            accent_color = '#ff6b35'
        WHERE slug = 'wr'
        """
    )
