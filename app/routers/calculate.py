import asyncio
import aiohttp
from fastapi import APIRouter
from fastapi.responses import JSONResponse
import json
import time
import hmac
import hashlib
import urllib.parse
from datetime import datetime, timezone
import os, random
from app.routers.trading_bot import get_buy_signals
# ============================================================
# CONFIGURATION
# ============================================================
router = APIRouter(prefix="/Python-BOT", tags=["Python-bot"])
TESTNET = True  # 🧪 True = Binance Testnet, False = Live trading

if TESTNET:
    BINANCE_BASE_URL = "https://testnet.binance.vision"
    print("🧪 Running in TESTNET mode (no real funds).")
else:
    BINANCE_BASE_URL = "https://api.binance.com"
    print("🚀 Running in LIVE mode (real trades will execute).")

API_KEY =  "yaWn3isqK3dkDBP4P9pi0rEaagzHfKBLLpJsJjQ4yCsc9SkPqLRzOExsOkjbCgCS"
API_SECRET = "lSADHDGy2nKswJfKju0k5qWrySqEyMUKZ6p5fikSCawzKULOSeKdjogOmx8YpDSf"

API_BASE = "https://backend.mytradegenius.com/binance_prices/latest_5m"
WS_URL = "wss://stream.binance.com:9443/stream?streams="

SLEEP_INTERVAL = 5           # seconds between TSL loops
WS_BATCH_SIZE = 200          # max streams per WebSocket
ENTRY_PRICE_UPDATE_HOURS = {1, 5, 9, 13, 17, 21}
ENTRY_PRICE_UPDATE_MINUTE = 41
MULTIPLIER = 3.5

# ============================================================
# GLOBAL STATE
# ============================================================


ENTRY_PRICES = {}     # symbol → entry price
ATR_CACHE = {}        # symbol → {"atr": float, "updated_at": timestamp}
LATEST_DATA = {}      # symbol → {"price": float, "last_update": datetime}
print(ENTRY_PRICES)
# ============================================================
# BINANCE API WRAPPER
# ============================================================
async def get_server_time():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.binance.com/api/v3/time") as res:
            data = await res.json()
            return data["serverTime"]
        
async def binance_request(method: str, path: str, params=None, signed=False):
    """
    Async Binance HTTP request supporting both Live and Testnet.
    """
    if params is None:
        params = {}

    if signed:
        server_time = await get_server_time()  # 🔹 sync Binance server time
        params["timestamp"] = server_time
        params["recvWindow"] = 5000
        query = urllib.parse.urlencode(params)
        signature = hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
        params["signature"] = signature

    headers = {"X-MBX-APIKEY": API_KEY}
    url = f"{BINANCE_BASE_URL}{path}"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.request(method, url, params=params, headers=headers) as res:
                try:
                    data = await res.json()
                except Exception:
                    data = await res.text()
                return {"status": res.status, "data": data}
        except Exception as e:
            print(f"❌ Binance API Error ({path}): {e}")
            return {"status": 0, "data": str(e)}

# ============================================================
# TRADE EXECUTION
# ============================================================
TRADE_LOGS = []  # List to store completed trade summaries
BOUGHT_SYMBOLS = set()

async def execute_buy(reason, price, time_, symbol, entry_amount=50, timeline=None):
    try:
        quantity = round(entry_amount // price, 5)
        payload = {"symbol": symbol, "side": "BUY", "type": "MARKET", "quantity": quantity}

        print(f"🟢 [BUY INITIATED] {symbol} @ {price:.5f} | Qty: {quantity} | Reason: {reason}")
        res = await binance_request("POST", "/api/v3/order", payload, signed=True)
        BOUGHT_SYMBOLS.add(symbol)
        trade = {
            "_id": f"TRADE-{symbol}-{int(datetime.utcnow().timestamp())}",
            "tradeId": f"AISUPERBOT-{int(datetime.utcnow().timestamp()*1000)}",
            "botId": {
                "_id": "690073a76542dfe6a1399ac4",
                "botName": "Python_Rakib"
            },
            "side": "BUY",
            "status": "COMPLETED",
            "asset": symbol,
            "pairQuote": "USDT",
            "exchange": "Binance",
            "buyDateTime": datetime.utcnow().isoformat() + "Z",
            "buyPrice": price,
            "quantity": quantity,
            "apiResponse": {
                "simulated": True,
                "modeTag": "ENTRY_BUY"
            },
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "updatedAt": datetime.utcnow().isoformat() + "Z",
            "__v": 0,
            "exchangeFees": round(price * quantity * 0.00055, 8),  # example fee calc
            "reason": reason,
        }
        TRADE_LOGS.append(trade)
        print(f"✅ Logged BUY trade for {symbol}")
        print(f"✅ [BUY SUCCESS] {symbol}")
        
    except Exception as e:
        print(f"❌ Binance BUY failed for {symbol}: {e}")

async def execute_sell(reason, price, time_, symbol, entry_price, entry_amount=50, timeline=None):
    try:
        quantity = round(entry_amount // entry_price, 5)
        payload = {"symbol": symbol, "side": "SELL", "type": "MARKET", "quantity": quantity}

        print(f"🔴 [SELL INITIATED] {symbol} @ {price:.5f} | Qty: {quantity} | Reason: {reason}")
        res = await binance_request("POST", "/api/v3/order", payload, signed=True)
        profit=price-entry_price
        for trade in TRADE_LOGS:
            if trade["asset"] == symbol and trade["side"] == "BUY" and "sellPrice" not in trade:
                trade.update({
                    "sellPrice": price,
                    "sellDateTime": datetime.utcnow().isoformat() + "Z",
                    "status": "COMPLETED",
                    "profit": profit,
                    "reason": reason,
                    "orderIdSell": f"SIM_SELL_{trade['tradeId']}"
                })
                print(f"💰 SELL updated for {symbol} | Profit: {profit:.2f}")
                break
    except Exception as e:
        print(f"❌ [SELL FAILED] {symbol} → {res['data']}")

# ============================================================
# ATR CALCULATION
# ============================================================

async def compute_atr(session, symbol: str, limit=35, period=14):
    try:
        async with session.get(f"{API_BASE}/{symbol}") as res:
            data = await res.json()
            candles = data.get(symbol, [])
            if not candles or len(candles) < period + 1:
                return None

            parsed = [{"open": float(c[1][1]), "high": float(c[1][2]),
                       "low": float(c[1][3]), "close": float(c[1][4])} for c in candles[-limit:]]

            trs = []
            for i in range(1, len(parsed)):
                prev_close = parsed[i - 1]["close"]
                high, low = parsed[i]["high"], parsed[i]["low"]
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                trs.append(tr)

            return sum(trs[-period:]) / period
    except Exception as e:
        print(f"[ATR ERROR] {symbol}: {e}")
        return None

async def get_cached_atr(session, symbol):
    now = time.time()
    if symbol in ATR_CACHE and now - ATR_CACHE[symbol]["updated_at"] < 60:
        return ATR_CACHE[symbol]["atr"]
    atr = await compute_atr(session, symbol)
    if atr:
        ATR_CACHE[symbol] = {"atr": atr, "updated_at": now}
    return atr

# ============================================================
# HYBRID TRAILING STOP LOGIC
# ============================================================

def get_hybrid_tsl(entry_price, profit_pct, elapsed_min, atr):
    STEP_PROFITS = [
        {"pct": 0.01, "tsl": lambda e: e * 0.995},
        {"pct": 0.02, "tsl": lambda e: e * 0.997},
        {"pct": 0.03, "tsl": lambda e: e * 0.999},
        {"pct": 0.05, "tsl": lambda e: e},
        {"pct": 0.08, "tsl": lambda e: e * 1.005},
        {"pct": 0.12, "tsl": lambda e: e * 1.01},
    ]

    tsl_base = entry_price - atr * MULTIPLIER
    step_lock = tsl_base

    for step in STEP_PROFITS:
        if profit_pct >= step["pct"]:
            step_lock = max(step_lock, step["tsl"](entry_price))

    tsl_time_elapsed = max(0, min(elapsed_min, 230))
    max_buffer_pct = 0.006
    min_buffer_pct = 0.0000001
    buffer_pct = max_buffer_pct - (max_buffer_pct - min_buffer_pct) * (tsl_time_elapsed / 230)
    time_based_tsl = entry_price * (1 - buffer_pct)

    return max(time_based_tsl, step_lock)
# ============================================================
# WEBSOCKET PRICE COLLECTOR
# ============================================================

async def ws_worker(symbol_batch):
    streams = [f"{s.lower()}@miniTicker" for s in symbol_batch]
    url = WS_URL + "/".join(streams)
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(url) as ws:
                    print(f"🔌 Connected to Binance WS for {len(symbol_batch)} symbols.")
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            payload = json.loads(msg.data).get("data")
                            if payload:
                                symbol = payload["s"].upper()
                                price = float(payload["c"])
                                LATEST_DATA[symbol] = {
                                    "price": price,
                                    "last_update": datetime.now(timezone.utc)
                                }
                        elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                            break
        except Exception as e:
            print(f"[WebSocket ERROR] {e}. Reconnecting in 5s...")
            await asyncio.sleep(5)

async def websocket_collector(symbols):
    tasks = []
    for i in range(0, len(symbols), WS_BATCH_SIZE):
        batch = symbols[i:i + WS_BATCH_SIZE]
        tasks.append(ws_worker(batch))
    await asyncio.gather(*tasks)
symbol_state={}
async def process_symbol(session, symbol, entry, price_info, elapsed_min):
    try:
        price = price_info["price"]
        profit_pct = (price / entry) - 1
        atr = await get_cached_atr(session, symbol)
        if atr is None:
            return

        tsl = get_hybrid_tsl(entry, profit_pct, elapsed_min, atr)
        tp1 = entry * 1.012
        tp2 = entry * 1.005

        print(
            f"[{datetime.utcnow():%H:%M:%S}] {symbol} | Price: {price:.5f} | "
            f"TSL: {tsl:.5f} | TP1: {tp1:.5f} | TP2: {tp2:.5f} | "
            f"Profit: {profit_pct*100:.3f}% | Time: {elapsed_min:.1f}m"
        )

        # --- SELL CONDITIONS ---
        """Check all sell conditions and execute sell if any is met."""
        # Get or initialize per-symbol state
        state = symbol_state.get(symbol, {
            "was_above_half": False,
            "tsl_touched": False,
            "price_near_tsl": False,
        })

        change_pct = ((price - entry) / entry) * 100
        current_time = datetime.utcnow()

        # ==============================================================
        # Condition 7: Hard Stop (-2%) after 10 mins
        # ==============================================================
        if elapsed_min > 10 and price <= entry * 0.98:
            await execute_sell("Hard Stop (-2%) after 10 mins", price, current_time, symbol, entry)
            return

        # ==============================================================
        # Phase 1 — Before 200 mins
        # ==============================================================
        if elapsed_min <= 200:

            # Condition 1: TP1 (1.2%)
            if change_pct >= 1.2:
                await execute_sell("TP1 (+1.2%) before 200 mins", price, current_time, symbol, entry)
                return

            # Condition 2: TP2 (fall below +0.5% after going above)
            if change_pct >= 0.5:
                state["was_above_half"] = True
            elif state["was_above_half"] and change_pct < 0.5:
                await execute_sell("TP2 fallback: Fell below +0.5% after going above before 200 mins", price, current_time, symbol, entry)
                return

        # ==============================================================
        # Phase 2 — After 200 mins (200–240)
        # ==============================================================
        elif 200 < elapsed_min <= 240:

            # Condition 3: Gradually reduce TP from 0.5% → 0.2%
            gradual_tp = 0.5 - ((elapsed_min - 200) / 40) * (0.5 - 0.2)  # Linear fade
            if change_pct >= gradual_tp:
                await execute_sell(f"Gradual TP reached ({gradual_tp:.2f}%) after 200 mins", price, current_time, symbol, entry)
                return

            # --- TSL-related conditions ---
            if tsl:

                # Condition 4: Sell if falls below TSL after 200 mins
                if price <= tsl:
                    await execute_sell("Price fell below TSL after 200 mins", price, current_time, symbol, entry)
                    return

                # Condition 5: Sell when price rises above TSL and falls
                if price > tsl:
                    state["tsl_touched"] = True
                elif state["tsl_touched"] and price < tsl:
                    await execute_sell("Price rose above TSL and fell after 200 mins", price, current_time, symbol, entry)
                    return

                # Condition 6: If below TSL, rises near TSL then falls
                if price < tsl:
                    if abs(price - tsl) / tsl < 0.001:  # within 0.1%
                        state["price_near_tsl"] = True
                    elif state["price_near_tsl"] and price < tsl:
                        await execute_sell("Price rose near TSL and fell again after 200 mins", price, current_time, symbol, entry)
                        return

        # ==============================================================
        # Condition 8: Time-based exit (240 mins)
        # ==============================================================
        elif elapsed_min >= 240:
            await execute_sell("Time-based exit (240 mins)", price, current_time, symbol, entry)
            return

        # ==============================================================
        # Save updated state
        # ==============================================================
        symbol_state[symbol] = state
    except Exception as e:
        print(f"[PROCESS ERROR] {symbol}: {e}")

# ============================================================
# MAIN TSL MONITOR LOOP
# ============================================================

async def tsl_monitor(SYMBOLS):
    start_time = time.time()
    async with aiohttp.ClientSession() as session:
        while True:
            loop_start = time.time()
            elapsed_min = (loop_start - start_time) / 60
            tasks = []

            for symbol in SYMBOLS:
                entry = ENTRY_PRICES.get(symbol)
                price_info = LATEST_DATA.get(symbol)
                if not entry or not price_info:
                    continue
                tasks.append(process_symbol(session, symbol, entry, price_info, elapsed_min))

            if tasks:
                await asyncio.gather(*tasks)

            loop_end = time.time()
            sleep_time = max(0, SLEEP_INTERVAL - (loop_end - loop_start))
            await asyncio.sleep(sleep_time)

async def fetch_entry_prices(symbols: list):
    """
    Capture entry prices from WebSocket live prices at specific hours & minute.
    ENTRY_PRICE_UPDATE_HOURS and ENTRY_PRICE_UPDATE_MINUTE define when to record.
    """
    recorded_today = set()  # Track which symbols have already recorded entry price

    while True:
        now = datetime.now(timezone.utc)
        # Check if current time matches any entry price update hour & minute
        if now.hour in ENTRY_PRICE_UPDATE_HOURS and now.minute == ENTRY_PRICE_UPDATE_MINUTE:
            for symbol in symbols:
                # Only record if not already recorded for this time slot
                if symbol not in recorded_today and symbol in LATEST_DATA:
                    ENTRY_PRICES[symbol] = LATEST_DATA[symbol]["price"]
                    recorded_today.add(symbol)
                    print(f"[{datetime.utcnow():%H:%M:%S}] ✅ Entry price recorded for {symbol}: {ENTRY_PRICES[symbol]:.5f}")
            # Sleep 60s to avoid multiple recordings within the same minute
            await asyncio.sleep(60)
        else:
            # Reset daily recording after the minute passes
            if now.minute != ENTRY_PRICE_UPDATE_MINUTE:
                recorded_today.clear()
            await asyncio.sleep(5)
            
# Fetch + execute buy
# --------------------------
async def fetch_and_execute_buy(user_id: str):
    # Use user's keys and run buy logic
    print(f"Executing buy for user {user_id}")
    try:
        buy_signals = await get_buy_signals()
        print("DEBUG: Raw buy signals:", buy_signals)
        strong_buy_symbols = buy_signals.get("strong_buy", [])
        print(f"🎯 Strong Buy Symbols: {strong_buy_symbols}")
    except Exception as e:
        print(f"[⚠️] Error fetching strong buy signals: {e}")
        strong_buy_symbols = []

    if not strong_buy_symbols:
        print("⚠️ No strong buy symbols found.")
        return

    # --- 🎲 Pick one token randomly ---
    symbol = random.choice(strong_buy_symbols)
    print(f"🎯 Randomly selected symbol for this run: {symbol}")

    # Start WebSocket collector for that token
    asyncio.create_task(websocket_collector([symbol]))
    print(f"🔌 WebSocket collector started for {symbol}")

    # Wait until latest price is available
    while symbol not in LATEST_DATA:
        await asyncio.sleep(0.5)

    entry_price = LATEST_DATA[symbol]["price"]
    ENTRY_PRICES[symbol] = entry_price

    await execute_buy(
        "Strong Buy",
        entry_price,
        datetime.utcnow(),
        symbol,
        50,
        "4h"
    )
    BOUGHT_SYMBOLS.add(symbol)
    print(f"⚡ BUY executed for {symbol} at {entry_price:.5f} | {datetime.utcnow().strftime('%H:%M:%S')} UTC")

    # Start TSL monitor for this symbol only
    asyncio.create_task(tsl_monitor({symbol}))
    print(f"⏱️ TSL monitor started for {symbol}")

@router.get("/trade-logs")
async def get_trade_logs():
    """
    Fetch all executed trades (buy/sell) as JSON.
    """
    return JSONResponse(content={"success": True, "count": len(TRADE_LOGS), "trade_logs": TRADE_LOGS})