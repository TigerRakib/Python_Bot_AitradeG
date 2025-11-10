"""add id (PK) and bot_name; make user_id unique (PostgreSQL)

Revision ID: c164b47d9886
Revises: 
Create Date: 2025-11-10 17:48:06.232478
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c164b47d9886"
down_revision: Union[str, Sequence[str], None] = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1) Add columns as nullable first (so DDL succeeds on existing data)
    with op.batch_alter_table("bots") as batch:
        batch.add_column(sa.Column("id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("bot_name", sa.String(), nullable=True, server_default="Default Bot"))

    # 2) Create sequence, set default, and init it so nextval() yields 1
    op.execute("CREATE SEQUENCE IF NOT EXISTS bots_id_seq OWNED BY bots.id")
    op.execute("ALTER TABLE bots ALTER COLUMN id SET DEFAULT nextval('bots_id_seq')")
    # init sequence so the next nextval() returns 1 (no '0 out of bounds' issue, no gaps)
    op.execute("SELECT setval('bots_id_seq', 1, false)")

    # 3) Backfill IDs for existing rows
    op.execute("UPDATE bots SET id = nextval('bots_id_seq') WHERE id IS NULL")

    # 4) Make new columns NOT NULL and drop server default on bot_name
    with op.batch_alter_table("bots") as batch:
        batch.alter_column("id", nullable=False)
        batch.alter_column("bot_name", nullable=False, server_default=None)

    # 5) Swap primary key from user_id -> id
    op.execute("ALTER TABLE bots DROP CONSTRAINT IF EXISTS bots_pkey")
    op.execute("ALTER TABLE bots ADD CONSTRAINT bots_pkey PRIMARY KEY (id)")

    # 6) Enforce one bot per user
    op.execute("ALTER TABLE bots ADD CONSTRAINT uq_bots_user_id UNIQUE (user_id)")

    # 7) Reset sequence to MAX(id) so future inserts use the next number
    op.execute("SELECT setval('bots_id_seq', (SELECT COALESCE(MAX(id), 1) FROM bots), true)")

    # 8) Helpful indexes (optional: PK already indexes id)
    op.execute("CREATE INDEX IF NOT EXISTS ix_bots_id ON bots (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_bots_user_id ON bots (user_id)")

def downgrade() -> None:
    # Reverse order: drop new PK, remove unique, make user_id PK again, drop columns.
    op.execute("DROP INDEX IF EXISTS ix_bots_user_id")
    op.execute("DROP INDEX IF EXISTS ix_bots_id")
    op.execute("ALTER TABLE bots DROP CONSTRAINT IF EXISTS uq_bots_user_id")
    op.execute("ALTER TABLE bots DROP CONSTRAINT IF EXISTS bots_pkey")
    op.execute("ALTER TABLE bots ADD CONSTRAINT bots_pkey PRIMARY KEY (user_id)")

    with op.batch_alter_table("bots") as batch:
        batch.drop_column("bot_name")
        batch.drop_column("id")

    # Optionally drop sequence (only if you created it here and nothing else depends on it)
    op.execute("DROP SEQUENCE IF EXISTS bots_id_seq")
