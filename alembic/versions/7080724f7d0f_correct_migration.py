"""correct migration

Revision ID: 7080724f7d0f
Revises: 583cfe3bc494
Create Date: 2025-11-27 02:49:27.023718

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7080724f7d0f'
down_revision: Union[str, Sequence[str], None] = '583cfe3bc494'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.alter_column(
        'transactions',
        'user_id',
        new_column_name='bot_id',
        existing_type=sa.String(),
        existing_nullable=True
    )


def downgrade():
    op.alter_column(
        'transactions',
        'bot_id',
        new_column_name='user_id',
        existing_type=sa.String(),
        existing_nullable=True
    )
