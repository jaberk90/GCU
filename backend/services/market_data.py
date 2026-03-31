"""
MarketDataService — FR-7
Uses Financial Modeling Prep (FMP) stable API endpoints.
Free tier: 250 calls/day, no IP blocking.
"""

import os
import time
import requests
import requests
import logging

logger  = logging.getLogger(__name__)
API_KEY = os.getenv("FMP_API_KEY", "")
BASE    = "https://financialmodelingprep.com/stable"

_cache: dict = {}
CACHE_TTL = 3600


def _get(endpoint: str, params: dict = {}) -> dict | list:
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


def _fmt(v, dec=2):
    try:
        return str(round(float(v), dec))
    except:
        return "—"


def _pct(v, dec=2):
    try:
        return str(round(float(v) * 100, dec)) + "%"
    except:
        return "—"


class MarketDataService:

    def __init__(self, symbol: str):
        self.symbol = symbol.upper()

    def get_quote(self) -> dict:
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
        try:
            data = _get("historical-price-eod/full",
                        {"symbol": self.symbol, "limit": 120})
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
        try:
            # Profile — name, sector, beta, market cap, 52w range
            profile_data = _get("profile", {"symbol": self.symbol})
            profile = profile_data[0] if isinstance(profile_data, list) and profile_data else {}

            # Ratios (annual) — exact field names confirmed from API response
            ratios_data = _get("ratios", {"symbol": self.symbol, "limit": 1})
            r = ratios_data[0] if isinstance(ratios_data, list) and ratios_data else {}

            # Key metrics (annual) — ROE, ROA, EV metrics
            km_data = _get("key-metrics", {"symbol": self.symbol, "limit": 1})
            km = km_data[0] if isinstance(km_data, list) and km_data else {}

            if not profile:
                return {}

            # 52w range — FMP format: "169.21-288.62"
            raw_range = str(profile.get("range", ""))
            w52_low, w52_high = "—", "—"
            if "-" in raw_range:
                parts = raw_range.split("-")
                if len(parts) >= 2:
                    w52_low  = _fmt(parts[0].strip())
                    w52_high = _fmt(parts[-1].strip())

            return {
                "Symbol":               self.symbol,
                "Name":                 profile.get("companyName", "—"),
                "Exchange":             profile.get("exchangeShortName", "—"),
                "Sector":               profile.get("sector", "—"),
                "Industry":             profile.get("industry", "—"),
                "Description":          profile.get("description", "—"),
                "MarketCapitalization": str(profile.get("marketCap", "")),
                # Valuation — from ratios annual
                "PERatio":              _fmt(r.get("priceToEarningsRatio")),
                "ForwardPE":            _fmt(r.get("priceToFreeCashFlowRatio")),
                "EPS":                  _fmt(r.get("netIncomePerShare")),
                "EVToEBITDA":           _fmt(km.get("evToEBITDA")),
                "PriceToBookRatio":     _fmt(r.get("priceToBookRatio")),
                # Profitability — multiply by 100 for percentage display
                "ReturnOnEquityTTM":    _pct(km.get("returnOnEquity")),
                "ReturnOnAssetsTTM":    _pct(km.get("returnOnAssets")),
                "ProfitMargin":         _pct(r.get("netProfitMargin")),
                "OperatingMarginTTM":   _pct(r.get("operatingProfitMargin")),
                "RevenueTTM":           _fmt(r.get("revenuePerShare")),
                # Health
                "Beta":                 _fmt(profile.get("beta")),
                "DividendYield":        _pct(r.get("dividendYield")),
                "BookValue":            _fmt(r.get("bookValuePerShare")),
                "SharesOutstanding":    str(profile.get("volAvg", "")),
                "52WeekHigh":           w52_high,
                "52WeekLow":            w52_low,
            }
        except Exception as e:
            logger.error("get_overview failed for %s: %s", self.symbol, e)
            return {}

    def get_rsi(self, period: int = 14) -> dict:
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
        daily = self.get_daily()
        return {
            "quote":    self.get_quote(),
            "daily":    daily,
            "overview": self.get_overview(),
            "rsi":      self.get_rsi(),
            "sma50":    self.get_sma(50),
        }
