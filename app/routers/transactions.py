from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Transaction,BotTradeState

router = APIRouter(prefix="/transactions", tags=["Transactions & Logs"])

@router.get("/bot/{user_id}")
async def get_bot_transactions(user_id: str, db: AsyncSession = Depends(get_db)):
    """
    Fetch all transactions (BUY/SELL) for a specific bot by bot_id.
    """
    try:
        result = await db.execute(
            select(Transaction).where(Transaction.user_id == user_id).order_by(Transaction.buy_time.desc())
        )
        transactions = result.scalars().all()

        if not transactions:
            return JSONResponse(content={"success": True, "user_id": user_id, "transactions": []})

        # Convert to dict for JSONResponse
        transactions_list = []
        for t in transactions:
            transactions_list.append({
                "id": t.id,
                "user_id": t.user_id,
                "bot_name": t.bot_name,
                "side": t.side,
                "status": t.status,
                "asset": t.asset,
                "pair_quote": t.pair_quote,
                "exchange": t.exchange,
                "quantity": t.quantity,
                "buy_price": t.buy_price,
                "sell_price": t.sell_price,
                "exchange_fees": t.exchange_fees,
                "profit": t.profit,
                "reason": t.reason,
                "buy_time": t.buy_time.isoformat() if t.buy_time else None,
                "sell_time": t.sell_time.isoformat() if t.sell_time else None,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            })

        return JSONResponse(content={"success": True, "user_id": user_id, "transactions": transactions_list})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching transactions: {e}")
    

@router.get("/trade_logs/{user_id}")
async def get_bot_current_state(user_id: str, db: AsyncSession = Depends(get_db)):
    """
    Fetch the current working state of a bot.
    """
    try:
        result = await db.execute(
            select(BotTradeState)
            .where(BotTradeState.user_id == user_id)
            .order_by(BotTradeState.updated_at.desc())
        )
        states = result.scalars().all()

        response = [
            {
                "time": s.updated_at.strftime("%d-%m-%Y, %H:%M:%S"),
                "action": s.action,
                "token": s.asset,
                "logs": s.logs
            }
            for s in states
        ]

        return JSONResponse({"success": True, "count": len(response), "states": response})

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)