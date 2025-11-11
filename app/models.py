from sqlalchemy import Column, String, Boolean, Float, DateTime, Enum,Integer,UniqueConstraint
from app.database import Base
from datetime import datetime
from sqlalchemy.sql import func


class Bot(Base):
    __tablename__ = "bots"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, unique=True, nullable=False) 
    bot_name = Column(String, nullable=False)
    user_id = Column(String, primary_key=True, index=True)
    api_key = Column(String, nullable=False)
    secret_key = Column(String, nullable=False)
    active = Column(Boolean, default=True)
    running = Column(Boolean, default=False)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_bots_user_id"),
    )
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, index=True)
    bot_id = Column(String, index=True)
    bot_name = Column(String)
    side = Column(Enum("BUY", "SELL", name="trade_side"))
    status = Column(Enum("Filled", "COMPLETED", name="trade_status"), default="Filled")
    asset = Column(String)
    pair_quote = Column(String, default="USDT")
    exchange = Column(String, default="Binance")
    quantity = Column(Float)
    buy_price = Column(Float, nullable=True)
    sell_price = Column(Float, nullable=True)
    exchange_fees = Column(Float, default=0.0)
    profit = Column(Float, nullable=True)
    reason = Column(String)
    buy_time = Column(DateTime, nullable=True)
    sell_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BotTradeState(Base):
    __tablename__ = "bot_trade_state"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    bot_id = Column(String, index=True)           # Bot identifier
    asset = Column(String, index=True)            # Token/symbol
    action = Column(String, default="HOLD")       # HOLD / BUY / SELL / COMPLETED
    price = Column(Float, nullable=True)          # Current price
    logs = Column(String, default="Monitoring active trade")  # Description
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())