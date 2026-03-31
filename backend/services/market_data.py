"""
MarketDataService — FR-7
Fetches and caches data from Alpha Vantage.
API key is loaded from environment (never exposed to frontend).
"""

import os
import time
import requests
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

BASE_URL   = "https://www.alphavantage.co/query"
API_KEY    = os.getenv("ALPHAVANTAGE_API_KEY", "")
CACHE_TTL  = int(os.getenv("CACHE_TTL_SECONDS", 3600))

_cache: dict = {}


def _get(params: dict) -> dict:
    """Fetch from Alpha Vantage with simple in-memory TTL cache."""
    cache_key = str(sorted(params.items()))
    cached = _cache.get(cache_key)
    if cached and (time.time() - cached["ts"]) < CACHE_TTL:
        logger.debug("Cache hit: %s", cache_key[:80])
        return cached["data"]

    params["apikey"] = API_KEY
    resp = requests.get(BASE_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    _cache[cache_key] = {"ts": time.time(), "data": data}
    return data


class MarketDataService:
    def get_quote(self, symbol: str) -> dict:
        data = _get({"function": "GLOBAL_QUOTE", "symbol": symbol})
        return data.get("Global Quote") or {}

    def get_daily(self, symbol: str, outputsize: str = "compact") -> dict:
        data = _get({"function": "TIME_SERIES_DAILY", "symbol": symbol, "outputsize": outputsize})
        return data.get("Time Series (Daily)") or {}

    def get_overview(self, symbol: str) -> dict:
        data = _get({"function": "OVERVIEW", "symbol": symbol})
        return data if data.get("Symbol") else {}

    def get_rsi(self, symbol: str, period: int = 14) -> dict:
        data = _get({"function": "RSI", "symbol": symbol, "interval": "daily",
                     "time_period": period, "series_type": "close"})
        return data.get("Technical Analysis: RSI") or {}

    def get_macd(self, symbol: str) -> dict:
        data = _get({"function": "MACD", "symbol": symbol, "interval": "daily", "series_type": "close"})
        return data.get("Technical Analysis: MACD") or {}

    def get_sma(self, symbol: str, period: int) -> dict:
        data = _get({"function": "SMA", "symbol": symbol, "interval": "daily",
                     "time_period": period, "series_type": "close"})
        return data.get(f"Technical Analysis: SMA") or {}
