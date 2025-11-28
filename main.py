# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.executors.asyncio import AsyncIOExecutor
from datetime import timezone
import asyncio

from app.routers.bot_manager import router as bot_manager_router, get_all_active_users
from app.routers.calculate import fetch_and_execute_buy
from app.routers.transactions import router as transactions_logs

from app.database import async_session
from app.models import Bot 
from sqlalchemy.future import select

app = FastAPI(title="Multi-User Trading Bot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bot_manager_router)
app.include_router(transactions_logs)
# Scheduler setup
executors = {
    "asyncio": AsyncIOExecutor(),
    "threadpool": ThreadPoolExecutor(4),
}

scheduler = AsyncIOScheduler(executors=executors, timezone=timezone.utc)

BUY_HOURS = [1, 5, 9, 13, 17,21]  # Every 4 hours
BUY_MINUTE = 15
# SELL_HOURS = [0, 4, 8, 12,14, 16, 2,]
# SELL_MINUTE = 51
# ==========================
# Global Scheduled Function
# ==========================
async def run_scheduled_buys():
    """Called every 4 hours for all active user bots."""
    print("🚀 Starting global buy cycle...")

    # 1) Load all active bots
    async with async_session() as db:
        result = await db.execute(select(Bot).where(Bot.active == True))
        bots = result.scalars().all()

        if not bots:
            print("⚠️ No active user found.")
            return
        
        # 2) Mark all these bots as running=True at the start of the cycle
        for b in bots:
            b.running = True
        await db.commit()

    # 3) Execute the strategy for each bot
    for b in bots:
        user_id = b.user_id
        bot_name = b.bot_name
        try:
            print(f"🤖 {bot_name} bot is running buy for user {user_id}")
            # if your function accepts both: await fetch_and_execute_buy(user_id, bot_name)
            await fetch_and_execute_buy(user_id, bot_name)
        except Exception as e:
            print(f"[⚠️] Error for user {user_id}: {e}")
        finally:
            # 4) Flip running=False for this bot after its scheduled run finishes
            async with async_session() as db:
                res = await db.execute(select(Bot).where(Bot.user_id == user_id))
                bot_row = res.scalar_one_or_none()
                if bot_row:
                    bot_row.running = False
                    await db.commit()

    print("✅ Finished all scheduled buys.")

# Root endpoint
@app.get("/")
def read_root():
    return {
        "message": "Python-Bot IS RUNNING",
        "status": "OK",
        "backend": "MYTRADEGENIUS Backend",
        "docs": "/docs",
        "redoc": "/redoc"
    }

# Health check endpoint
@app.get("/health")
def health_check():
    return {"status": "healthy"}

# ==========================
# Startup Event
# ==========================
@app.on_event("startup")
async def startup_event():
    # Run immediately at startup
    # asyncio.create_task(run_scheduled_buys())

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
