"""modify transactions table

Revision ID: 583cfe3bc494
Revises: 2cb4beb103d9
Create Date: 2025-11-15 01:20:33.697878

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '583cfe3bc494'
down_revision: Union[str, Sequence[str], None] = '2cb4beb103d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename bot_id column to user_id"""
    op.alter_column('transactions', 'bot_id', new_column_name='user_id')


def downgrade() -> None:
    """Revert column name back to bot_id"""
    op.alter_column('transactions', 'user_id', new_column_name='bot_id')