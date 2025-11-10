from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

# PostgreSQL async URL (note: +asyncpg)
DATABASE_URL = "postgresql+asyncpg://postgres:arbigobot123@127.0.0.1:5432/mytradegenius"

# Create async engine
engine = create_async_engine(DATABASE_URL, echo=False)

# Create async session
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

# Dependency for FastAPI routes
async def get_db():
    async with async_session() as session:
        yield session
