"""add start_time and end_time to bots

Revision ID: 3e8b7effe1c9
Revises: c164b47d9886
Create Date: 2025-11-11 16:09:53.649568

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3e8b7effe1c9'
down_revision: Union[str, Sequence[str], None] = 'c164b47d9886'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add start_time column with default as current UTC time
    op.add_column('bots', sa.Column('start_time', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')))
    
    # Add end_time column (nullable for now, can be set when bot is created)
    op.add_column('bots', sa.Column('end_time', sa.DateTime(), nullable=True))



def downgrade() -> None:
    # Drop the columns if rolling back
    op.drop_column('bots', 'start_time')
    op.drop_column('bots', 'end_time')
