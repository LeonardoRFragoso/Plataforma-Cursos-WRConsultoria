"""add_is_required_to_lesson_and_material_fields

Revision ID: 2b91da1c9b95
Revises: 212453bf1615
Create Date: 2026-08-19 21:30:44.700722

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b91da1c9b95'
down_revision: Union[str, None] = '212453bf1615'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_required column to lessons (defaults True, backfills existing rows)
    op.add_column(
        'lessons',
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default=sa.text('true')),
    )
    # Backfill: all existing lessons become required (safe default)
    op.execute("UPDATE lessons SET is_required = true WHERE is_required IS NULL OR is_required = false")

    # Add new columns to lesson_materials for backend-managed storage
    op.add_column('lesson_materials', sa.Column('storage_key', sa.String(), nullable=True))
    op.add_column('lesson_materials', sa.Column('mime_type', sa.String(), nullable=True))
    op.add_column('lesson_materials', sa.Column('size_bytes', sa.Integer(), nullable=True))
    # Make file_url nullable for new records that use storage_key instead
    op.alter_column('lesson_materials', 'file_url',
               existing_type=sa.String(),
               nullable=True)


def downgrade() -> None:
    op.alter_column('lesson_materials', 'file_url',
               existing_type=sa.String(),
               nullable=False)
    op.drop_column('lesson_materials', 'size_bytes')
    op.drop_column('lesson_materials', 'mime_type')
    op.drop_column('lesson_materials', 'storage_key')
    op.drop_column('lessons', 'is_required')
