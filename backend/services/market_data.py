"""
MarketDataService — FR-7
Uses Financial Modeling Prep (FMP) stable API endpoints (post Aug 2025).
Free tier: 250 calls/day, no IP blocking.
"""

import os
import time
import requests
import logging

logger  = logging.getLogger(__name__)
API_KEY = os.getenv("FMP_API_KEY", "")
BASE    = "https://financialmodelingprep.com/stable"

_cache: dict = {}
CACHE_TTL = 3600


def _get(endpoint: str, params: dict = {}) -> dict | list:
    """GET from FMP stable API with TTL cache."""
    cache_key = endpoint + str(sorted(params.items()))
    cached = _cache.get(cache_key)
    if cached and (time.time() - cached["ts"]) < CACHE_TTL:
        return cached["data"]

    all_params = {"apikey": API_KEY, **params}
    try:
        resp = requests.get(f"{BASE}/{endpoint}", params=all_params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error("FMP request failed [%s]: %s", endpoint, e)
        return {}

    if isinstance(data, dict) and ("Error Message" in data or "message" in data):
        logger.warning("FMP error [%s]: %s", endpoint,
                       data.get("Error Message") or data.get("message"))
        return {}

    _cache[cache_key] = {"ts": time.time(), "data": data}
    return data


class MarketDataService:

    def __init__(self, symbol: str):
        self.symbol = symbol.upper()

    def get_quote(self) -> dict:
        """Real-time quote."""
        try:
            data = _get("quote", {"symbol": self.symbol})
            if not data or not isinstance(data, list):
                return {}
            q = data[0]
            change     = round(float(q.get("change", 0)), 2)
            change_pct = round(float(q.get("changesPercentage", 0)), 2)
            return {
                "05. price":          str(round(float(q.get("price", 0)), 2)),
                "09. change":         str(change),
                "10. change percent": f"{change_pct}%",
                "02. open":           str(round(float(q.get("open", 0)), 2)),
                "03. high":           str(round(float(q.get("dayHigh", 0)), 2)),
                "04. low":            str(round(float(q.get("dayLow", 0)), 2)),
                "08. previous close": str(round(float(q.get("previousClose", 0)), 2)),
                "06. volume":         str(int(q.get("volume", 0))),
            }
        except Exception as e:
            logger.error("get_quote failed for %s: %s", self.symbol, e)
            return {}

    def get_daily(self) -> dict:
        """Historical daily OHLCV — 6 months."""
        try:
            data = _get("historical-price-eod/full",
                        {"symbol": self.symbol, "limit": 180})
            if not data or not isinstance(data, list):
                return {}
            result = {}
            for row in data:
                result[row["date"]] = {
                    "1. open":   str(round(float(row.get("open",  0)), 2)),
                    "2. high":   str(round(float(row.get("high",  0)), 2)),
                    "3. low":    str(round(float(row.get("low",   0)), 2)),
                    "4. close":  str(round(float(row.get("close", 0)), 2)),
                    "5. volume": str(int(row.get("volume", 0))),
                }
            return result
        except Exception as e:
            logger.error("get_daily failed for %s: %s", self.symbol, e)
            return {}

    def get_overview(self) -> dict:
        """Company profile + key metrics."""
        try:
            profile_data = _get("profile", {"symbol": self.symbol})
            profile = profile_data[0] if isinstance(profile_data, list) and profile_data else {}

            metrics_data = _get("key-metrics", {"symbol": self.symbol, "limit": 1})
            metrics = metrics_data[0] if isinstance(metrics_data, list) and metrics_data else {}

            if not profile:
                return {}

            def fmt(v, dec=2):
                try:
                    return str(round(float(v), dec))
                except:
                    return "—"

            return {
                "Symbol":               self.symbol,
                "Name":                 profile.get("companyName", "—"),
                "Exchange":             profile.get("exchangeShortName", "—"),
                "Sector":               profile.get("sector", "—"),
                "Industry":             profile.get("industry", "—"),
                "Description":          profile.get("description", "—"),
                "MarketCapitalization": str(profile.get("mktCap", "")),
                "PERatio":              fmt(metrics.get("peRatio")),
                "ForwardPE":            fmt(metrics.get("pfcfRatio")),
                "EPS":                  fmt(metrics.get("netIncomePerShare")),
                "EVToEBITDA":           fmt(metrics.get("evToFreeCashFlow")),
                "PriceToBookRatio":     fmt(metrics.get("pbRatio")),
                "ReturnOnEquityTTM":    fmt(metrics.get("roe")),
                "ReturnOnAssetsTTM":    fmt(metrics.get("returnOnTangibleAssets")),
                "ProfitMargin":         fmt(metrics.get("netProfitMargin")),
                "OperatingMarginTTM":   fmt(metrics.get("operatingProfitMargin")),
                "RevenueTTM":           str(metrics.get("revenuePerShare", "")),
                "Beta":                 fmt(profile.get("beta")),
                "DividendYield":        fmt(metrics.get("dividendYield")),
                "BookValue":            fmt(metrics.get("bookValuePerShare")),
                "SharesOutstanding":    str(profile.get("volAvg", "")),
                "52WeekHigh":           fmt(profile.get("range", "").split("-")[-1]
                                           if "-" in str(profile.get("range","")) else None),
                "52WeekLow":            fmt(profile.get("range", "").split("-")[0]
                                           if "-" in str(profile.get("range","")) else None),
            }
        except Exception as e:
            logger.error("get_overview failed for %s: %s", self.symbol, e)
            return {}

    def get_rsi(self, period: int = 14) -> dict:
        """RSI calculated from daily price history."""
        try:
            daily  = self.get_daily()
            dates  = sorted(daily.keys())
            closes = [float(daily[d]["4. close"]) for d in dates]
            if len(closes) < period + 1:
                return {}
            gains, losses = [], []
            for i in range(1, len(closes)):
                diff = closes[i] - closes[i - 1]
                gains.append(max(diff, 0))
                losses.append(max(-diff, 0))
            avg_gain = sum(gains[:period]) / period
            avg_loss = sum(losses[:period]) / period
            rsi_vals = []
            for i in range(period, len(gains)):
                avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i]) / period
                rs = avg_gain / avg_loss if avg_loss != 0 else 100
                rsi_vals.append(100 - (100 / (1 + rs)))
            return {dates[period + i]: {"RSI": str(round(r, 2))}
                    for i, r in enumerate(rsi_vals)}
        except Exception as e:
            logger.error("get_rsi failed for %s: %s", self.symbol, e)
            return {}

    def get_sma(self, period: int = 50) -> dict:
        """SMA calculated from daily price history."""
        try:
            daily  = self.get_daily()
            dates  = sorted(daily.keys())
            closes = [float(daily[d]["4. close"]) for d in dates]
            if len(closes) < period:
                return {}
            result = {}
            for i in range(period - 1, len(closes)):
                sma = sum(closes[i - period + 1:i + 1]) / period
                result[dates[i]] = {"SMA": str(round(sma, 2))}
            return result
        except Exception as e:
            logger.error("get_sma failed for %s: %s", self.symbol, e)
            return {}

    def fetch_all(self) -> dict:
        """Fetch all data — daily is cached so RSI/SMA reuse it."""
        daily = self.get_daily()
        return {
            "quote":    self.get_quote(),
            "daily":    daily,
            "overview": self.get_overview(),
            "rsi":      self.get_rsi(),
            "sma50":    self.get_sma(50),
        }
