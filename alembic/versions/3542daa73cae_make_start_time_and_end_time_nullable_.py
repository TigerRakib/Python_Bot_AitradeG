"""make start_time and end_time nullable in bots

Revision ID: 3542daa73cae
Revises: 3e8b7effe1c9
Create Date: 2025-11-11 16:23:58.566545

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3542daa73cae'
down_revision: Union[str, Sequence[str], None] = '3e8b7effe1c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Alter columns to be nullable
    op.alter_column('bots', 'start_time',
               existing_type=sa.DateTime(),
               nullable=True)
    op.alter_column('bots', 'end_time',
               existing_type=sa.DateTime(),
               nullable=True)


def downgrade():
    # Revert columns to non-nullable
    op.alter_column('bots', 'start_time',
               existing_type=sa.DateTime(),
               nullable=False)
    op.alter_column('bots', 'end_time',
               existing_type=sa.DateTime(),
               nullable=False)
