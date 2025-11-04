# create_tables.py

from app.database import Base, engine
from app.models import Bot
from sqlalchemy import inspect
print("Connecting to database:", engine.url)

# Create the bots table
Base.metadata.create_all(bind=engine)

print("Bots table created successfully!")
inspector = inspect(engine)
print("Tables in database:", inspector.get_table_names())