"""Change default active to False

Revision ID: 2cb4beb103d9
Revises: 3542daa73cae
Create Date: 2025-11-13 17:45:05.762211

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2cb4beb103d9'
down_revision: Union[str, Sequence[str], None] = '3542daa73cae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to set default active=False."""
    op.alter_column(
        'bots',
        'active',
        server_default=sa.text('false')
    )


def downgrade() -> None:
    """Downgrade schema to set default active=True."""
    op.alter_column(
        'bots',
        'active',
        server_default=sa.text('true')
    )