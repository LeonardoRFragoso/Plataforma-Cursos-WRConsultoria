"""add_course_cover_media_fields

Revision ID: e5f6a7b8c9d0
Revises: 2b91da1c9b95
Create Date: 2026-08-20 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "2b91da1c9b95"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("courses", sa.Column("cover_image_url", sa.String(), nullable=True))
    op.add_column("courses", sa.Column("cover_image_alt", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("courses", "cover_image_alt")
    op.drop_column("courses", "cover_image_url")
