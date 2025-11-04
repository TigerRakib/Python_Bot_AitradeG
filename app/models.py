from sqlalchemy import Column, String, Boolean
from app.database import Base

class Bot(Base):
    __tablename__ = "bots"

    user_id = Column(String, primary_key=True, index=True)
    api_key = Column(String, nullable=False)
    secret_key = Column(String, nullable=False)
    active = Column(Boolean, default=True)
    running = Column(Boolean, default=False)
