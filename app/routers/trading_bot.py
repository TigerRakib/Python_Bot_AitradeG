import asyncio
import httpx
from typing import List, Dict, Any
ADVANCED_URL = "https://backend01.aisuperbot.org/api/v1/ai/four-hour-advanced/live"
SIMPLE_URL = "https://backend01.aisuperbot.org/api/v1/python/predictions"
SIGNALS_URL = "https://backend04.aisuperbot.org/api/v1/signals"


async def fetch_json(url: str) -> Any:
    """Fetch JSON data asynchronously."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[⚠️] Error fetching {url}: {e}")
            return None


def normalize_symbol(symbol: str) -> str:
    """Remove 'USDT' suffix and trim."""
    return symbol.replace("USDT", "").strip() if symbol else ""


async def get_buy_signals() -> Dict[str, Any]:
    """Fetch and merge buy signals from all three APIs."""

    # Fetch all APIs concurrently
    advanced_task = asyncio.create_task(fetch_json(ADVANCED_URL))
    simple_task = asyncio.create_task(fetch_json(SIMPLE_URL))
    signals_task = asyncio.create_task(fetch_json(SIGNALS_URL))

    advanced_data, simple_data, signals_data = await asyncio.gather(
        advanced_task, simple_task, signals_task
    )

    # --- Filters ---
    filtered_advanced = [
        p for p in (advanced_data.get("data") or [])
        if str(p.get("signal", "")).lower() == "buy"
    ] if advanced_data else []

    filtered_simple = [
        s for s in (simple_data or [])
        if str(s.get("prediction_status", "")).lower().startswith("buy")
    ] if simple_data else []

    filtered_signals = [
        s for s in (signals_data.get("signals") or [])
        if s.get("indicatorsTriggered", {}).get("buy", {}).get("firstCheckPassed") is True
    ] if signals_data else []

    # --- Combine ---
    seen: Dict[str, Dict[str, Any]] = {}

    # Advanced predictions
    for p in filtered_advanced:
        sym = normalize_symbol(p.get("symbol"))
        if sym not in seen:
            seen[sym] = {
                "symbol": sym,
                "asset_name": p.get("asset_name"),
                "isPredictionBuy": True,
                "isSimplePredictionBuy": False,
                "technicalIndicators5minBuy": False,
            }
        else:
            seen[sym]["isPredictionBuy"] = True

    # Simple predictions
    for s in filtered_simple:
        sym = normalize_symbol(s.get("symbol"))
        if sym not in seen:
            seen[sym] = {
                "symbol": sym,
                "asset_name": s.get("asset_name"),
                "isPredictionBuy": False,
                "isSimplePredictionBuy": True,
                "technicalIndicators5minBuy": False,
            }
        else:
            seen[sym]["isSimplePredictionBuy"] = True

    # 5-min signals
    for s in filtered_signals:
        sym = normalize_symbol(s.get("symbol"))
        if sym not in seen:
            seen[sym] = {
                "symbol": sym,
                "asset_name": s.get("asset_name"),
                "isPredictionBuy": False,
                "isSimplePredictionBuy": False,
                "technicalIndicators5minBuy": True,
            }
        else:
            seen[sym]["technicalIndicators5minBuy"] = True

    combined_data = sorted(seen.values(), key=lambda x: x.get("asset_name", ""))
    # print(combined_data)
    # --- Strong Buy (at least 2 sources) ---
    appear_all=[]
    strong_buy_signals = []
    for item in combined_data:
        count= sum([
            item["isPredictionBuy"],
            item["isSimplePredictionBuy"],
            item["technicalIndicators5minBuy"],]
        )
        if count>=2:
            strong_buy_signals.append(item)
        if count==3:
            appear_all.append(item["symbol"]+"USDT")
    # print(appear_all)
    SYMBOLS = [s["symbol"] + "USDT" for s in strong_buy_signals]
    return {
        "strong_buy": SYMBOLS,
        "all_3":appear_all,
        }



# async def main():
#     results = await get_buy_signals()
#     strong_buy_tokens = [s["symbol"] for s in results["strong_buy"]]
#     print(strong_buy_tokens)
#     print("\n✅ Strong Buy Tokens:")
#     print(", ".join(strong_buy_tokens))

# asyncio.run(main())

