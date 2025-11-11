# app/routers/bot_manager.py
from fastapi import APIRouter, Depends, HTTPException,Query
from datetime import datetime, timedelta
from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from app.models import Bot, Transaction
from app import schemas
from app.database import async_session, get_db
import asyncio
from app.routers.calculate import fetch_and_execute_buy, execute_sell

router = APIRouter(prefix="/bots", tags=["Bot Manager"])


# ✅ Create Bot
@router.post("/create")
async def create_bot(bot: schemas.BotCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new bot for a user if it doesn't already exist.
    Enforced by DB: user_id is unique (one bot per user).
    """
    # Friendly pre-check (DB unique still the source of truth)
    result = await db.execute(select(Bot).where(Bot.user_id == bot.user_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Bot already exists for this user")
    
    new_bot = Bot(
        user_id=bot.user_id,
        bot_name=bot.bot_name,
        api_key=bot.api_key,
        secret_key=bot.secret_key,
        active=True,
        running=False,
        start_time=None,
        end_time=None,
    )
    db.add(new_bot)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Bot already exists for this user")

    await db.refresh(new_bot)
    return {"message": f"✅ Bot '{new_bot.bot_name}' created for user {new_bot.user_id}"}


# Start Bot (by user)
@router.post("/start/{user_id}")
async def start_bot(user_id: str,duration_days: int = Query(..., description="Bot duration in days, must be 2 or 7"), db: AsyncSession = Depends(get_db)):
    """
    Start a bot for a specific user & bot_name if it exists.
    Marks the DB record as running and launches the async task.
    """
    # Validate duration_days
    if duration_days not in (2, 7):
        raise HTTPException(status_code=422, detail="duration_days must be 2 or 7")

    # 1) Ensure bot exists and is active
    result = await db.execute(
        select(Bot).where(and_(Bot.user_id == user_id))
    )
    user_record = result.scalar_one_or_none()
    if not user_record:
        raise HTTPException(status_code=404, detail="❌ User not found in the site")

    else:
        bot_name=user_record.bot_name
    if user_record.running:
        raise HTTPException(status_code=400, detail=" User Bot is running currently")
    start_time = datetime.utcnow()
    end_time = start_time + timedelta(days=duration_days)
    asyncio.create_task(fetch_and_execute_buy(user_id,bot_name))
    

    # 5) Mark DB record running
    user_record.running = True
    user_record.start_time = start_time
    user_record.end_time = end_time

    await db.commit()

    return {
        "success": True,
        "message": f"Bot '{user_record.bot_name}' started for user {user_record.user_id}",
        "bot": {
            "_id": str(user_record.id),
            "userId": str(user_record.user_id),
            "botName": user_record.bot_name,
            "isActive": user_record.active,
            "startTime": user_record.start_time.isoformat(),
            "endTime": user_record.end_time.isoformat()
        }
    }


# 🛑 Stop Bot (by user)
@router.post("/stop/{user_id}")
async def stop_bot(user_id: str, db: AsyncSession = Depends(get_db)):
    """
    Stop a running bot for a specific user & bot_name.
    Before stopping, attempt to close any open BUY position for that user.
    """
    # 1) Load bot record
    result = await db.execute(
        select(Bot).where(and_(Bot.user_id == user_id))
    )
    user_record = result.scalar_one_or_none()

    if not user_record:
        raise HTTPException(status_code=404, detail="No active user found for this bot")
    else:
        bot_name=user_record.bot_name
    # 2) Try to sell the most recent filled BUY for this user
    print(f"🟡 Checking for open positions before stopping {bot_name} (user {user_id})...")
    result = await db.execute(
        select(Transaction)
        .where(Transaction.bot_id == user_id)           
        .where(Transaction.side == "BUY")
        .where(Transaction.status == "Filled")
        .order_by(Transaction.buy_time.desc())
    )
    trade = result.scalars().first()

    if trade:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://api.binance.com/api/v3/ticker/price?symbol={trade.asset}"
                )
                current_price = float(resp.json()["price"])

            # If execute_sell accepts user context, add it here.
            await execute_sell(
                reason="🛑 Manual Bot Stop",
                price=current_price,
                time_=datetime.utcnow(),
                symbol=trade.asset,
                entry_price=trade.buy_price,
            )
            print(f"✅ Sold {trade.asset} before stopping {bot_name} (user {user_id})")

            # Update transaction record
            trade.sell_price = current_price
            trade.sell_time = datetime.utcnow()
            trade.side = "SELL"
            trade.status = "COMPLETED"
            trade.profit = round(
                (current_price - trade.buy_price) * trade.quantity - trade.exchange_fees,
                8,
            )
            await db.commit()
        except Exception as e:
            print(f"⚠️ Error while selling before stopping bot: {e}")

    # 4) Mark DB record stopped
    user_record.running = False
    await db.commit()

    return {"message": f"🛑 Bot '{bot_name}' stopped for user {user_id} (any open positions sold)"}

# Internal helper (can be called from anywhere)
async def fetch_all_active_users():
    """
    Fetch all users who currently have an active bot.
    Since each user can have only one bot, this gives unique active users.
    """
    async with async_session() as db:
        result = await db.execute(
            select(Bot.user_id, Bot.bot_name)
            .where(Bot.active == True)
        )
        rows = result.all()
        return [{"user_id": r.user_id, "bot_name": r.bot_name} for r in rows]


# FastAPI route
@router.get("/active_users")
async def get_all_active_users(_: AsyncSession = Depends(get_db)):
    """
    Return all users who currently have an active & running bot.
    Useful to monitor total active users.
    """
    active_users = await fetch_all_active_users()
    return {
        "active_user_count": len(active_users),
        "active_users": active_users,
    }
