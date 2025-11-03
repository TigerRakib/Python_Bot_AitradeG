import requests

def fetch_symbol_name_map() -> dict[str, str]:
    """
    Fetches a mapping of SYMBOL → Coin Name from CoinGecko.
    Returns uppercase symbol keys for lookup, e.g.:
    { 'BTC': 'Bitcoin', 'ETH': 'Ethereum' }
    """
    url = "https://api.coingecko.com/api/v3/coins/list"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise exception for HTTP errors
        coins = response.json()
        # Map symbol (uppercase) to name
        for coin in coins:
            if coin["symbol"]=="nom":
                print(coin)
    except Exception as e:
        print(f"[✖] Failed to fetch CoinGecko symbol map: {e}")
        return {}

# Example usage
if __name__ == "__main__":
    mapping = fetch_symbol_name_map()
