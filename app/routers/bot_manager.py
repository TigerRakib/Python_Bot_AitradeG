# app/routers/bot_manager.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Bot
from sqlalchemy.future import select
from app import models, schemas
from app.database import get_db
import asyncio
from app.routers.calculate import fetch_and_execute_buy
router = APIRouter(prefix="/bots", tags=["Bot Manager"])

# Example in-memory store
USER_BOTS = {}

# ✅ Create Bot
@router.post("/create")
async def create_bot(bot: schemas.BotCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new bot for a user if it doesn't already exist.
    """
    result = await db.execute(select(Bot).where(Bot.user_id == bot.user_id))
    existing_bot = result.scalar_one_or_none()

    if existing_bot:
        raise HTTPException(status_code=400, detail="Bot already exists for this user")

    new_bot = Bot(
        user_id=bot.user_id,
        api_key=bot.api_key,
        secret_key=bot.secret_key,
        active=True,
        running=False,
    )

    db.add(new_bot)
    await db.commit()
    await db.refresh(new_bot)

    return {"message": f"✅ Bot created for user {bot.user_id}"}


# ✅ Start Bot
@router.post("/start/{user_id}")
async def start_bot(user_id: str, db: AsyncSession = Depends(get_db)):
    """
    Start the bot manually for a user — only if it exists in the bots table.
    """
    # 1️⃣ Check if the bot exists in DB
    result = await db.execute(select(Bot).where(Bot.user_id == user_id))
    bot_record = result.scalar_one_or_none()

    if not bot_record:
        raise HTTPException(status_code=404, detail="❌ Bot not found in database")

    # 2️⃣ Check if bot is already running in memory
    bot = USER_BOTS.get(user_id)
    if bot and bot["running"]:
        return {"message": f"⚙️ Bot already running for {user_id}"}

    # 3️⃣ Create new bot entry in memory if needed
    if not bot:
        USER_BOTS[user_id] = {"running": False, "task": None}
        bot = USER_BOTS[user_id]

    # 4️⃣ Start async task
    bot["running"] = True
    task = asyncio.create_task(fetch_and_execute_buy(user_id))
    bot["task"] = task

    # 5️⃣ Update DB (mark running=True)
    bot_record.running = True
    await db.commit()

    return {"message": f"🚀 Bot started successfully for {user_id}"}


# Stop Bot
@router.post("/stop/{user_id}")
async def stop_bot(user_id: str, db: AsyncSession = Depends(get_db)):
    """
    Stop a running bot manually for a given user.
    """
    result = await db.execute(select(Bot).where(Bot.user_id == user_id))
    bot_record = result.scalar_one_or_none()

    if not bot_record or not bot_record.running:
        raise HTTPException(status_code=404, detail="❌ No active bot found for this user")

    # Mark as stopped in DB
    bot_record.running = False
    await db.commit()

    return {"message": f"🛑 Bot stopped for {user_id}"}


@router.get("/active")
async def get_all_active_bots():
    """
    Return all active bots (for the scheduler)
    """
    return [bot for bot in USER_BOTS.values() if bot["active"]]
