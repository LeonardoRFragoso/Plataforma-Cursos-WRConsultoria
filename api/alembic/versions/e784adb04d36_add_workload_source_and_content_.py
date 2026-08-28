"""add_workload_source_and_content_approval_fields

Revision ID: e784adb04d36
Revises: 9193813510de
Create Date: 2026-08-28 17:56:50.172934

Adds regulatory workload provenance fields to course_compliance_profiles
and content approval audit trail fields to course_content_profiles.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e784adb04d36"
down_revision: Union[str, None] = "9193813510de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Regulatory workload provenance on compliance profiles
    op.add_column(
        "course_compliance_profiles",
        sa.Column(
            "workload_source",
            sa.String(64),
            nullable=False,
            server_default="REVIEW_REQUIRED",
        ),
    )
    op.add_column(
        "course_compliance_profiles",
        sa.Column("workload_minutes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "course_compliance_profiles",
        sa.Column("normative_minimum_minutes", sa.Integer(), nullable=True),
    )

    # Content approval audit trail on content profiles
    op.add_column(
        "course_content_profiles",
        sa.Column("approved_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "course_content_profiles",
        sa.Column(
            "approved_by",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "course_content_profiles",
        sa.Column("manifest_version", sa.String(128), nullable=True),
    )
    op.add_column(
        "course_content_profiles",
        sa.Column("manifest_hash", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("course_content_profiles", "manifest_hash")
    op.drop_column("course_content_profiles", "manifest_version")
    op.drop_column("course_content_profiles", "approved_by")
    op.drop_column("course_content_profiles", "approved_at")
    op.drop_column("course_compliance_profiles", "normative_minimum_minutes")
    op.drop_column("course_compliance_profiles", "workload_minutes")
    op.drop_column("course_compliance_profiles", "workload_source")
