from fastapi import APIRouter
import httpx
import asyncio
from datetime import datetime

router = APIRouter(
    prefix="/active-users",
    tags=["Active Users"]
)

ACTIVE_USERS_URL = "https://bot01.mytradegenius.com/bots/active_users"
TRANSACTION_URL = "https://bot01.mytradegenius.com/transactions/bot/"


async def fetch_active_users():
    async with httpx.AsyncClient() as client:
        resp = await client.get(ACTIVE_USERS_URL, timeout=15)
        resp.raise_for_status()
        return resp.json()


async def fetch_latest_transaction(user_id: str):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{TRANSACTION_URL}{user_id}", timeout=15)
        resp.raise_for_status()
        data = resp.json()

    transactions = data.get("transactions", [])

    if not transactions:
        return None

    # Auto-detect latest by buy_time
    transactions.sort(
        key=lambda x: datetime.fromisoformat(x["buy_time"]) if x.get("buy_time") else datetime.min,
        reverse=True
    )

    return transactions[0]  # latest only


@router.get("/get_all_info")
async def get_all_info():
    active_users_data = await fetch_active_users()
    active_users = active_users_data.get("active_users", [])

    async def process_user(user):
        user_id = user.get("user_id")
        latest_tx = await fetch_latest_transaction(user_id)
        return {
            "user": user,
            "lastTransaction": latest_tx
        }

    # Parallel fetch
    results = await asyncio.gather(*(process_user(u) for u in active_users))

    return {"Success": True, "count": len(results), "bots": results}
