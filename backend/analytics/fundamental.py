"""
FundamentalAnalytics — FR-4 / US-4
Parses FMP overview response into structured fundamental metrics.
Handles pre-formatted strings from market_data.py gracefully.
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def _num(val, decimals=2):
    """Parse numeric value — returns float or None."""
    try:
        return round(float(str(val).replace("%", "").replace("$", "").strip()), decimals)
    except (TypeError, ValueError):
        return None


def _pass(val):
    """Pass value through as-is — already formatted by market_data.py."""
    if val is None or val == "" or val == "—":
        return "—"
    return str(val)


def _fmtB(val):
    """Format large number to B/T string."""
    try:
        n = float(str(val).replace(",", "").strip())
        if abs(n) >= 1e12: return f"${n/1e12:.2f}T"
        if abs(n) >= 1e9:  return f"${n/1e9:.2f}B"
        if abs(n) >= 1e6:  return f"${n/1e6:.2f}M"
        return f"${n:,.0f}"
    except:
        return "—"


class FundamentalAnalytics:

    def __init__(self, overview: dict):
        self.ov = overview

    def metrics(self) -> dict:
        ov = self.ov
        return {
            "company":     ov.get("Name")        or "—",
            "sector":      ov.get("Sector")      or "—",
            "industry":    ov.get("Industry")    or "—",
            "exchange":    ov.get("Exchange")    or "—",
            "description": ov.get("Description") or "—",
            "valuation": {
                "pe_ratio":   _num(ov.get("PERatio")),
                "forward_pe": _num(ov.get("ForwardPE")),
                "eps":        _num(ov.get("EPS")),
                "ev_ebitda":  _num(ov.get("EVToEBITDA")),
                "price_book": _num(ov.get("PriceToBookRatio")),
                "market_cap": _fmtB(ov.get("MarketCapitalization")),
            },
            "profitability": {
                "roe":              _pass(ov.get("ReturnOnEquityTTM")),
                "roa":              _pass(ov.get("ReturnOnAssetsTTM")),
                "profit_margin":    _pass(ov.get("ProfitMargin")),
                "operating_margin": _pass(ov.get("OperatingMarginTTM")),
                "revenue_ttm":      _pass(ov.get("RevenueTTM")),
            },
            "health": {
                "beta":           _num(ov.get("Beta")),
                "dividend_yield": _pass(ov.get("DividendYield")),
                "book_value":     _num(ov.get("BookValue")),
                "52w_high":       _num(ov.get("52WeekHigh")),
                "52w_low":        _num(ov.get("52WeekLow")),
            }
        }
