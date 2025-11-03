# app/routers/bot_manager.py
from fastapi import APIRouter, HTTPException
import asyncio
from app.routers.calculate import fetch_and_execute_buy
router = APIRouter(prefix="/bots", tags=["Bot Manager"])

# Example in-memory store
USER_BOTS = {}

@router.post("/create")
async def create_bot(user_id: str, api_key: str, secret_key: str):
    USER_BOTS[user_id] = {
        "user_id": user_id,
        "api_key": api_key,
        "secret_key": secret_key,
        "active": True,
        "running":False,
    }
    return {"message": f"Bot created for {user_id}"}

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
