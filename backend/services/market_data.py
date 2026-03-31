"""
MarketDataService — FR-7
Fetches data from Alpha Vantage free tier.
Parallel requests for speed, with caching and error handling.
"""

import os
import time
import requests
import logging
import concurrent.futures

logger = logging.getLogger(__name__)

BASE_URL  = "https://www.alphavantage.co/query"
API_KEY   = os.getenv("ALPHAVANTAGE_API_KEY", "")
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", 3600))

_cache: dict = {}


def _get(params: dict) -> dict:
    """Fetch from Alpha Vantage with TTL cache."""
    cache_key = str(sorted(params.items()))
    cached = _cache.get(cache_key)
    if cached and (time.time() - cached["ts"]) < CACHE_TTL:
        logger.debug("Cache hit: %s", list(params.values())[:2])
        return cached["data"]

    params["apikey"] = API_KEY
    try:
        resp = requests.get(BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error("API request failed: %s", e)
        return {}

    # Detect rate limit responses — log but don't cache
    if "Information" in data or "Note" in data:
        msg = data.get("Information") or data.get("Note") or ""
        logger.warning("Alpha Vantage notice: %s", msg[:120])
        return {}

    _cache[cache_key] = {"ts": time.time(), "data": data}
    return data


class MarketDataService:

    def get_quote(self, symbol: str) -> dict:
        data = _get({"function": "GLOBAL_QUOTE", "symbol": symbol})
        return data.get("Global Quote") or {}

    def get_daily(self, symbol: str) -> dict:
        data = _get({"function": "TIME_SERIES_DAILY",
                     "symbol": symbol, "outputsize": "compact"})
        return data.get("Time Series (Daily)") or {}

    def get_overview(self, symbol: str) -> dict:
        data = _get({"function": "OVERVIEW", "symbol": symbol})
        return data if data.get("Symbol") else {}

    def get_rsi(self, symbol: str, period: int = 14) -> dict:
        data = _get({"function": "RSI", "symbol": symbol,
                     "interval": "daily", "time_period": period,
                     "series_type": "close"})
        return data.get("Technical Analysis: RSI") or {}

    def get_sma(self, symbol: str, period: int) -> dict:
        data = _get({"function": "SMA", "symbol": symbol,
                     "interval": "daily", "time_period": period,
                     "series_type": "close"})
        return data.get("Technical Analysis: SMA") or {}

    def fetch_all(self, symbol: str) -> dict:
        """Fetch all endpoints in parallel for speed."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            f_quote    = ex.submit(self.get_quote,    symbol)
            f_daily    = ex.submit(self.get_daily,    symbol)
            f_overview = ex.submit(self.get_overview, symbol)
            f_rsi      = ex.submit(self.get_rsi,      symbol)
            f_sma50    = ex.submit(self.get_sma,      symbol, 50)

        return {
            "quote":    f_quote.result(),
            "daily":    f_daily.result(),
            "overview": f_overview.result(),
            "rsi":      f_rsi.result(),
            "sma50":    f_sma50.result(),
        }
