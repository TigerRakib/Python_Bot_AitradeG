# app/main.py
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.executors.asyncio import AsyncIOExecutor
from datetime import timezone
import asyncio

from app.routers.bot_manager import router as bot_manager_router, get_all_active_bots
from app.routers.calculate import fetch_and_execute_buy

app = FastAPI(title="Multi-User Trading Bot")

app.include_router(bot_manager_router)

# Scheduler setup
executors = {
    "asyncio": AsyncIOExecutor(),
    "threadpool": ThreadPoolExecutor(4),
}

scheduler = AsyncIOScheduler(executors=executors, timezone=timezone.utc)

BUY_HOURS = [0, 4, 8, 12, 16, 20]  # Every 4 hours
BUY_MINUTE = 10


# ==========================
# Global Scheduled Function
# ==========================
async def run_scheduled_buys():
    """Called every 4 hours for all active user bots."""
    print("🚀 Starting global buy cycle...")
    active_bots = await get_all_active_bots()  # returns list of {user_id, api_key, secret_key, etc.}

    if not active_bots:
        print("⚠️ No active bots found.")
        return

    for bot in active_bots:
        user_id = bot["user_id"]
        try:
            print(f"🤖 Running buy for user {user_id}")
            await fetch_and_execute_buy(user_id)
        except Exception as e:
            print(f"[⚠️] Error for user {user_id}: {e}")

    print("✅ Finished all scheduled buys.")


# ==========================
# Startup Event
# ==========================
@app.on_event("startup")
async def startup_event():
    # Run immediately at startup
    asyncio.create_task(run_scheduled_buys())

    # Schedule every 4 hours
    scheduler.add_job(
        run_scheduled_buys,
        'cron',
        hour=','.join(map(str, BUY_HOURS)),
        minute=BUY_MINUTE,
        id="global_buy_job",
        replace_existing=True
    )
    scheduler.start()
    print(f"🕐 Global buy job scheduled at hours {BUY_HOURS}, minute {BUY_MINUTE} UTC")


@app.on_event("shutdown")
async def shutdown_scheduler():
    scheduler.shutdown()
