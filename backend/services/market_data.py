"""
MarketDataService — FR-7
Fetches data from Alpha Vantage free tier endpoints only.
Sequential calls with delay to respect 5 calls/minute rate limit.
"""

import os
import time
import requests
import logging

logger = logging.getLogger(__name__)

BASE_URL  = "https://www.alphavantage.co/query"
API_KEY   = os.getenv("ALPHAVANTAGE_API_KEY", "")
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", 3600))
CALL_DELAY = 13  # seconds between calls — stays safely under 5/min limit

_cache: dict = {}


def _get(params: dict) -> dict:
    """Fetch from Alpha Vantage with TTL cache. Sequential — never parallel."""
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

    # Detect rate limit or premium-required responses
    if "Information" in data or "Note" in data:
        msg = data.get("Information") or data.get("Note") or ""
        logger.warning("Alpha Vantage notice: %s", msg[:120])
        return {}

    _cache[cache_key] = {"ts": time.time(), "data": data}
    return data


class MarketDataService:

    def get_quote(self, symbol: str) -> dict:
        data = _get({"function": "GLOBAL_QUOTE", "symbol": symbol})
        time.sleep(CALL_DELAY)
        return data.get("Global Quote") or {}

    def get_daily(self, symbol: str) -> dict:
        # outputsize=compact = last 100 days, FREE on all plans
        data = _get({"function": "TIME_SERIES_DAILY",
                     "symbol": symbol, "outputsize": "compact"})
        time.sleep(CALL_DELAY)
        return data.get("Time Series (Daily)") or {}

    def get_overview(self, symbol: str) -> dict:
        data = _get({"function": "OVERVIEW", "symbol": symbol})
        time.sleep(CALL_DELAY)
        return data if data.get("Symbol") else {}

    def get_rsi(self, symbol: str, period: int = 14) -> dict:
        data = _get({"function": "RSI", "symbol": symbol,
                     "interval": "daily", "time_period": period,
                     "series_type": "close"})
        time.sleep(CALL_DELAY)
        return data.get("Technical Analysis: RSI") or {}

    def get_sma(self, symbol: str, period: int) -> dict:
        data = _get({"function": "SMA", "symbol": symbol,
                     "interval": "daily", "time_period": period,
                     "series_type": "close"})
        time.sleep(CALL_DELAY)
        return data.get("Technical Analysis: SMA") or {}
