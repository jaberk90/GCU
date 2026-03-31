"""
FundamentalAnalytics — FR-4 / US-4
Parses Alpha Vantage OVERVIEW response into structured fundamental metrics.
Gracefully handles missing values (FR-4 requirement).
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def _pct(val):
    """Convert decimal string to percentage string, or return '—'."""
    try:
        return f"{float(val) * 100:.2f}%"
    except (TypeError, ValueError):
        return "—"


def _num(val, decimals=2):
    try:
        return round(float(val), decimals)
    except (TypeError, ValueError):
        return None


class FundamentalAnalytics:

    def __init__(self, overview: dict):
        self.ov = overview

    def metrics(self) -> dict:
        ov = self.ov
        return {
            "company":       ov.get("Name")            or "—",
            "sector":        ov.get("Sector")          or "—",
            "industry":      ov.get("Industry")        or "—",
            "exchange":      ov.get("Exchange")        or "—",
            "description":   ov.get("Description")     or "—",
            "valuation": {
                "pe_ratio":     _num(ov.get("PERatio")),
                "forward_pe":   _num(ov.get("ForwardPE")),
                "eps":          _num(ov.get("EPS")),
                "ev_ebitda":    _num(ov.get("EVToEBITDA")),
                "price_book":   _num(ov.get("PriceToBookRatio")),
                "price_sales":  _num(ov.get("PriceToSalesRatioTTM")),
                "market_cap":   ov.get("MarketCapitalization") or "—",
            },
            "profitability": {
                "roe":             _pct(ov.get("ReturnOnEquityTTM")),
                "roa":             _pct(ov.get("ReturnOnAssetsTTM")),
                "profit_margin":   _pct(ov.get("ProfitMargin")),
                "operating_margin":_pct(ov.get("OperatingMarginTTM")),
                "revenue_ttm":     ov.get("RevenueTTM")         or "—",
                "gross_profit_ttm":ov.get("GrossProfitTTM")     or "—",
            },
            "health": {
                "beta":             _num(ov.get("Beta")),
                "dividend_yield":   _pct(ov.get("DividendYield")),
                "book_value":       _num(ov.get("BookValue")),
                "shares_outstanding":ov.get("SharesOutstanding") or "—",
                "52w_high":         _num(ov.get("52WeekHigh")),
                "52w_low":          _num(ov.get("52WeekLow")),
            }
        }
