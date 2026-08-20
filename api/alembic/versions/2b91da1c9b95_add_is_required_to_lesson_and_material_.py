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
    # Check if is_required column already exists (idempotent migration)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    lessons_columns = [col['name'] for col in inspector.get_columns('lessons')]
    
    if 'is_required' not in lessons_columns:
        # Add is_required column to lessons (defaults True, backfills existing rows)
        op.add_column(
            'lessons',
            sa.Column('is_required', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        )
        # Backfill: all existing lessons become required (safe default)
        op.execute("UPDATE lessons SET is_required = true WHERE is_required IS NULL OR is_required = false")

    # Add new columns to lesson_materials for backend-managed storage
    materials_columns = [col['name'] for col in inspector.get_columns('lesson_materials')]
    
    if 'storage_key' not in materials_columns:
        op.add_column('lesson_materials', sa.Column('storage_key', sa.String(), nullable=True))
    
    if 'mime_type' not in materials_columns:
        op.add_column('lesson_materials', sa.Column('mime_type', sa.String(), nullable=True))
    
    if 'size_bytes' not in materials_columns:
        op.add_column('lesson_materials', sa.Column('size_bytes', sa.Integer(), nullable=True))
    
    # Make file_url nullable for new records that use storage_key instead
    if 'file_url' in materials_columns:
        # Check if it's already nullable
        file_url_col = next((col for col in inspector.get_columns('lesson_materials') if col['name'] == 'file_url'), None)
        if file_url_col and not file_url_col['nullable']:
            op.alter_column('lesson_materials', 'file_url',
                       existing_type=sa.String(),
                       nullable=True)


def downgrade() -> None:
    # Check if columns exist before dropping (idempotent downgrade)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    materials_columns = [col['name'] for col in inspector.get_columns('lesson_materials')]
    lessons_columns = [col['name'] for col in inspector.get_columns('lessons')]
    
    # Restore file_url to NOT NULL if it exists
    if 'file_url' in materials_columns:
        file_url_col = next((col for col in inspector.get_columns('lesson_materials') if col['name'] == 'file_url'), None)
        if file_url_col and file_url_col['nullable']:
            op.alter_column('lesson_materials', 'file_url',
                       existing_type=sa.String(),
                       nullable=False)
    
    # Drop new columns only if they exist
    if 'size_bytes' in materials_columns:
        op.drop_column('lesson_materials', 'size_bytes')
    
    if 'mime_type' in materials_columns:
        op.drop_column('lesson_materials', 'mime_type')
    
    if 'storage_key' in materials_columns:
        op.drop_column('lesson_materials', 'storage_key')
    
    if 'is_required' in lessons_columns:
        op.drop_column('lessons', 'is_required')
