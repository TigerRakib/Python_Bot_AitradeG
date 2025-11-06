# create_transactions_table.py

import asyncio
from sqlalchemy import inspect
from app.database import engine
from app.models import BotTradeState  # only import the table you want

async def create_table():
    async with engine.begin() as conn:
        # Create only the Transaction table
        await conn.run_sync(BotTradeState.__table__.create, checkfirst=True)
    print("✅ Transaction table created successfully!")

    # Optional: Inspect tables
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
        print("Tables in database:", tables)

if __name__ == "__main__":
    asyncio.run(create_table())
