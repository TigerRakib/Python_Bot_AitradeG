# app/routers/bot_manager.py
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Bot,Transaction
from sqlalchemy.future import select
from app import models, schemas
from app.database import async_session,get_db
import asyncio
from app.routers.calculate import fetch_and_execute_buy,execute_sell
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
    # 1 Check if the bot exists in DB
    result = await db.execute(select(Bot).where(Bot.user_id == user_id))
    bot_record = result.scalar_one_or_none()

    if not bot_record:
        raise HTTPException(status_code=404, detail="❌ Bot not found in database")

    # 2️ Check if bot is already running in memory
    bot = USER_BOTS.get(user_id)
    if bot and bot["running"]:
        return {"message": f"⚙️ Bot already running for {user_id}"}

    # 3️ Create new bot entry in memory if needed
    if not bot:
        USER_BOTS[user_id] = {"running": False, "task": None}
        bot = USER_BOTS[user_id]

    # 4️ Start async task
    bot["running"] = True
    task = asyncio.create_task(fetch_and_execute_buy(user_id))
    bot["task"] = task

    # 5️ Update DB (mark running=True)
    bot_record.running = True
    await db.commit()

    return {"message": f"🚀 Bot started successfully for {user_id}"}


# Stop Bot
@router.post("/stop/{user_id}")
async def stop_bot(user_id: str, db: AsyncSession = Depends(get_db)):
    """
    Stop a running bot manually for a given user.
    Before stopping, automatically sell any open (BUY) positions.
    """
    # Find the bot
    result = await db.execute(select(Bot).where(Bot.user_id == user_id))
    bot_record = result.scalar_one_or_none()

    if not bot_record or not bot_record.running:
        raise HTTPException(status_code=404, detail="❌ No active bot found for this user")

    print(f"🟡 Checking for open positions before stopping {user_id}...")

    # Find latest open BUY trade for this user
    result = await db.execute(
        select(Transaction)
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

            await execute_sell(
                reason="🛑 Manual Bot Stop",
                price=current_price,
                time_=datetime.utcnow(),
                symbol=trade.asset,
                entry_price=trade.buy_price,
            )
            print(f"✅ Sold {trade.asset} before stopping {user_id}")
            
            # Update transaction
            trade.sell_price = current_price
            trade.sell_time = datetime.utcnow()
            trade.side = "SELL"
            trade.status = "COMPLETED"
            trade.profit = round((current_price - trade.buy_price) * trade.quantity - trade.exchange_fees, 8)
            await db.commit()
        except Exception as e:
            print(f"⚠️ Error while selling before stopping bot: {e}")

    # Mark bot as stopped
    bot_record.running = False
    await db.commit()

    return {"message": f"🛑 Bot stopped for {user_id} (any open positions sold)"}

# Internal helper (can be called from anywhere)
async def fetch_all_active_bots():
    async with async_session() as db:
        query = select(Bot).where(Bot.active == True)
        result = await db.execute(query)
        bots = result.scalars().all()
        return [{"user_id": b.user_id, "api_key": b.api_key, "secret_key": b.secret_key} for b in bots]


# FastAPI route
@router.get("/active")
async def get_all_active_bots(db: AsyncSession = Depends(get_db)):
    bots = await fetch_all_active_bots()
    return {"count": len(bots), "active_bots": bots}
