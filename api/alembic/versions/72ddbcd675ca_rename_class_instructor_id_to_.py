"""rename class instructor_id to responsible_admin_id

Revision ID: 72ddbcd675ca
Revises: a7438f7a1ab2
Create Date: 2026-08-13 13:45:17.866712

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '72ddbcd675ca'
down_revision: Union[str, None] = 'a7438f7a1ab2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('classes', 'instructor_id', new_column_name='responsible_admin_id')


def downgrade() -> None:
    op.alter_column('classes', 'responsible_admin_id', new_column_name='instructor_id')
