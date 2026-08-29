"""add compliance_blockers JSONB column to course_compliance_profiles

Revision ID: g8c9d0e1f2a3
Revises: f7a8b9c0d1e2
Create Date: 2026-08-29

Adds a ``compliance_blockers`` JSONB NOT NULL DEFAULT '[]' column to
``course_compliance_profiles``. This column stores compliance blockers
(e.g. COURSE_FIELD_HISTORY_CONFLICT, NR18_VARIANT_CONFIRMATION_REQUIRED)
separately from academic prerequisites, which remain in the ``prerequisites``
Text column.

Existing profiles receive an empty array. The column is NOT NULL with a
server default of ``'[]'::jsonb`` so every row always has a valid list.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "g8c9d0e1f2a3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "course_compliance_profiles",
        sa.Column(
            "compliance_blockers",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("course_compliance_profiles", "compliance_blockers")
