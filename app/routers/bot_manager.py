# app/routers/bot_manager.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import SessionLocal, engine
import asyncio
from app.routers.calculate import fetch_and_execute_buy
router = APIRouter(prefix="/bots", tags=["Bot Manager"])

# Example in-memory store
USER_BOTS = {}

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/create")
async def create_bot(bot: schemas.BotCreate, db: Session = Depends(get_db)):
    existing_bot = db.query(models.Bot).filter(models.Bot.user_id == bot.user_id).first()
    if existing_bot:
        raise HTTPException(status_code=400, detail="Bot already exists for this user")

    new_bot = models.Bot(
        user_id=bot.user_id,
        api_key=bot.api_key,
        secret_key=bot.secret_key,
        active=True,
        running=False,
    )
    db.add(new_bot)
    db.commit()
    db.refresh(new_bot)

    return {"message": f"Bot created for {bot.user_id}"}

@router.post("/start/{user_id}")
async def start_bot(user_id: str):
    """
    Start the bot manually for a user (runs fetch_and_execute_buy)
    """
    bot = USER_BOTS.get(user_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    if bot["running"]:
        return {"message": f"Bot already running for {user_id}"}

    bot["running"] = True
    # Run bot in background
    task = asyncio.create_task(fetch_and_execute_buy(user_id))
    bot["task"] = task

    return {"message": f"🚀 Bot started for {user_id}"}


@router.post("/stop/{user_id}")
async def stop_bot(user_id: str):
    """
    Stop a user's bot manually
    """
    bot = USER_BOTS.get(user_id)
    if not bot or not bot["running"]:
        raise HTTPException(status_code=404, detail="No active bot found for this user")

    bot["running"] = False
    task = bot.get("task")
    if task and not task.done():
        task.cancel()
        bot["task"] = None

    return {"message": f"🛑 Bot stopped for {user_id}"}


@router.get("/active")
async def get_all_active_bots():
    """
    Return all active bots (for the scheduler)
    """
    return [bot for bot in USER_BOTS.values() if bot["active"]]
