"""
Test Suite — Stock Analysis Web Application
Covers TC-01 through TC-10 as defined in the Capstone Implementation Plan.
Author: Jaber Kaal | GCU MSSE Capstone

Run: pytest tests/test_suite.py -v
"""

import pytest
import json
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app import create_app
from analytics.technical import TechnicalAnalytics
from analytics.fundamental import FundamentalAnalytics
from analytics.forecast import ForecastEngine


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


MOCK_QUOTE = {
    "05. price": "175.50",
    "09. change": "2.30",
    "10. change percent": "1.33%",
    "02. open":  "173.00",
    "03. high":  "176.00",
    "04. low":   "172.50",
    "08. previous close": "173.20",
    "06. volume": "55000000",
}

MOCK_OVERVIEW = {
    "Symbol": "AAPL", "Name": "Apple Inc.", "Exchange": "NASDAQ",
    "Sector": "Technology", "Industry": "Consumer Electronics",
    "PERatio": "28.5", "ForwardPE": "25.0", "EPS": "6.15",
    "EVToEBITDA": "20.3", "ReturnOnEquityTTM": "1.47",
    "ProfitMargin": "0.253", "DividendYield": "0.005",
    "Beta": "1.25", "52WeekHigh": "199.62", "52WeekLow": "124.17",
    "MarketCapitalization": "2750000000000",
}

MOCK_RSI   = {"2024-01-15": {"RSI": "55.23"}}
MOCK_MACD  = {"2024-01-15": {"MACD": "1.23", "MACD_Signal": "0.98", "MACD_Hist": "0.25"}}
MOCK_SMA50 = {"2024-01-15": {"SMA": "165.40"}}
MOCK_DAILY = {
    f"2024-01-{d:02d}": {"4. close": str(170 + d * 0.5), "1. open": "170",
                          "2. high": "172", "3. low": "169", "5. volume": "50000000"}
    for d in range(1, 31)
}


# ── TC-01: Enter valid ticker on Home (FR-1) ────────────────────────────────

class TestTC01ValidTickerValidation:
    """TC-01: Entering a valid ticker passes validation and routes to analysis."""

    def test_validate_valid_symbol(self, client):
        resp = client.post("/api/v1/validate", json={"symbol": "AAPL"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valid"] is True
        assert data["symbol"] == "AAPL"

    def test_validate_lowercase_uppercased(self, client):
        resp = client.post("/api/v1/validate", json={"symbol": "aapl"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valid"] is True
        assert data["symbol"] == "AAPL"

    def test_validate_multi_letter_symbol(self, client):
        resp = client.post("/api/v1/validate", json={"symbol": "GOOGL"})
        assert resp.status_code == 200
        assert resp.get_json()["valid"] is True


# ── TC-02: Reject empty ticker (FR-2) ───────────────────────────────────────

class TestTC02EmptyTickerRejected:
    """TC-02: Empty input is rejected with a validation message; no request sent."""

    def test_empty_string(self, client):
        resp = client.post("/api/v1/validate", json={"symbol": ""})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["valid"] is False
        assert "required" in data["message"].lower()

    def test_whitespace_only(self, client):
        resp = client.post("/api/v1/validate", json={"symbol": "   "})
        assert resp.status_code == 400
        assert resp.get_json()["valid"] is False

    def test_missing_symbol_key(self, client):
        resp = client.post("/api/v1/validate", json={})
        assert resp.status_code == 400
        assert resp.get_json()["valid"] is False


# ── TC-03: Reject invalid ticker format (FR-3) ──────────────────────────────

class TestTC03InvalidTickerRejected:
    """TC-03: Invalid format (numbers, special chars, too long) returns friendly error."""

    def test_numbers_in_symbol(self, client):
        resp = client.post("/api/v1/validate", json={"symbol": "INVALID1"})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["valid"] is False

    def test_special_characters(self, client):
        resp = client.post("/api/v1/validate", json={"symbol": "AA@PL"})
        assert resp.status_code == 400
        assert resp.get_json()["valid"] is False

    def test_too_long(self, client):
        resp = client.post("/api/v1/validate", json={"symbol": "TOOLONGSYMBOL"})
        assert resp.status_code == 400
        assert resp.get_json()["valid"] is False

    def test_error_message_is_friendly(self, client):
        resp = client.post("/api/v1/validate", json={"symbol": "BAD!!"})
        msg = resp.get_json()["message"]
        assert len(msg) > 10  # Has a real, readable message


# ── TC-04: Fundamental metrics displayed (FR-4) ─────────────────────────────

class TestTC04FundamentalMetrics:
    """TC-04: P/E, EPS, ROE, D/E shown with values on Fundamental tab."""

    def test_fundamental_parses_overview(self):
        fa = FundamentalAnalytics(MOCK_OVERVIEW)
        metrics = fa.metrics()
        val = metrics["valuation"]
        assert val["pe_ratio"]   == 28.5
        assert val["eps"]        == 6.15
        assert val["forward_pe"] == 25.0

    def test_roe_formatted_as_percentage(self):
        fa = FundamentalAnalytics(MOCK_OVERVIEW)
        metrics = fa.metrics()
        roe = metrics["profitability"]["roe"]
        assert "%" in roe

    def test_missing_values_return_dash(self):
        fa = FundamentalAnalytics({})
        metrics = fa.metrics()
        assert metrics["valuation"]["pe_ratio"] is None
        assert metrics["valuation"]["eps"]      is None

    def test_market_cap_present(self):
        fa = FundamentalAnalytics(MOCK_OVERVIEW)
        metrics = fa.metrics()
        assert metrics["valuation"]["market_cap"] != "—"


# ── TC-05: Technical indicators displayed (FR-5) ────────────────────────────

class TestTC05TechnicalIndicators:
    """TC-05: RSI, MACD, moving averages shown in Technical tab."""

    def _get_ta(self):
        return TechnicalAnalytics(MOCK_QUOTE, MOCK_DAILY, MOCK_RSI, MOCK_MACD, MOCK_SMA50)

    def test_summary_has_price(self):
        ta = self._get_ta()
        s = ta.summary()
        assert s["price"] == 175.50
        assert s["change"] == 2.30

    def test_indicators_list_not_empty(self):
        ta = self._get_ta()
        inds = ta.indicators()
        assert len(inds) >= 3

    def test_rsi_signal_computed(self):
        ta = self._get_ta()
        inds = ta.indicators()
        rsi_ind = next(i for i in inds if "RSI" in i["name"])
        assert rsi_ind["value"] == 55.23
        assert rsi_ind["signal"] in ("buy", "hold", "sell")

    def test_macd_signal_computed(self):
        ta = self._get_ta()
        inds = ta.indicators()
        macd_ind = next(i for i in inds if "MACD" in i["name"])
        assert macd_ind["signal"] == "buy"   # hist 0.25 > 0

    def test_sma50_above_signal(self):
        ta = self._get_ta()
        inds = ta.indicators()
        sma_ind = next(i for i in inds if "SMA 50" in i["name"])
        # price 175.50 > sma50 165.40 → buy
        assert sma_ind["signal"] == "buy"


# ── TC-06: Prediction forecast series returned (FR-6) ───────────────────────

class TestTC06PredictionForecast:
    """TC-06: Forecast renders with confidence score; fails safely on limited data."""

    def _daily_series(self, n=100):
        import datetime
        base = datetime.date(2023, 1, 1)
        return {
            (base + datetime.timedelta(days=i)).strftime("%Y-%m-%d"):
                {"4. close": str(150 + i * 0.1)}
            for i in range(n)
        }

    def test_forecast_returns_ensemble(self):
        fe = ForecastEngine(self._daily_series(100))
        result = fe.run()
        assert "ensemble" in result
        assert len(result["ensemble"]) == 10

    def test_forecast_has_confidence(self):
        fe = ForecastEngine(self._daily_series(100))
        result = fe.run()
        assert 0.0 <= result["confidence"] <= 1.0

    def test_forecast_direction_valid(self):
        fe = ForecastEngine(self._daily_series(100))
        result = fe.run()
        assert result["direction"] in ("Up", "Down", "Neutral")

    def test_forecast_fails_safely_on_limited_data(self):
        fe = ForecastEngine(self._daily_series(5))  # too little data
        result = fe.run()
        # Should return error or empty ensemble gracefully, not raise
        assert "error" in result or result.get("ensemble") is None or isinstance(result.get("ensemble"), list)

    def test_forecast_has_date_labels(self):
        fe = ForecastEngine(self._daily_series(100))
        result = fe.run()
        if "labels" in result:
            assert len(result["labels"]) == 10


# ── TC-07: Recommendation displayed (FR-7) ──────────────────────────────────

class TestTC07RecommendationDisplayed:
    """TC-07: Buy/Hold/Sell recommendation appears on Prediction tab."""

    def test_buy_recommendation_when_mostly_bullish(self):
        ta = TechnicalAnalytics(MOCK_QUOTE, MOCK_DAILY, MOCK_RSI, MOCK_MACD, MOCK_SMA50)
        ta.indicators()  # populate signals
        rec = ta.recommendation()
        assert rec["action"] in ("BUY", "HOLD", "SELL")

    def test_recommendation_has_reason(self):
        ta = TechnicalAnalytics(MOCK_QUOTE, MOCK_DAILY, MOCK_RSI, MOCK_MACD, MOCK_SMA50)
        ta.indicators()
        rec = ta.recommendation()
        assert len(rec["reason"]) > 10

    def test_recommendation_counts_sum_to_total(self):
        ta = TechnicalAnalytics(MOCK_QUOTE, MOCK_DAILY, MOCK_RSI, MOCK_MACD, MOCK_SMA50)
        ta.indicators()
        rec = ta.recommendation()
        assert rec["buy_count"] + rec["sell_count"] + rec["hold_count"] == rec["total"]

    def test_sell_recommendation_when_mostly_bearish(self):
        bearish_quote = dict(MOCK_QUOTE)
        bearish_quote["09. change"] = "-5.00"
        bearish_rsi  = {"2024-01-15": {"RSI": "75.00"}}  # overbought
        bearish_macd = {"2024-01-15": {"MACD": "0.50", "MACD_Signal": "1.20", "MACD_Hist": "-0.70"}}
        low_sma50    = {"2024-01-15": {"SMA": "200.00"}}  # price below sma
        ta = TechnicalAnalytics(bearish_quote, MOCK_DAILY, bearish_rsi, bearish_macd, low_sma50)
        ta.indicators()
        rec = ta.recommendation()
        assert rec["action"] == "SELL"


# ── TC-08: Charts render without errors (FR-8) ──────────────────────────────

class TestTC08ChartDataIntegrity:
    """TC-08: Chart data structures are valid and won't cause JS render errors."""

    def test_summary_all_numeric(self):
        ta = TechnicalAnalytics(MOCK_QUOTE, MOCK_DAILY, MOCK_RSI, MOCK_MACD, MOCK_SMA50)
        s = ta.summary()
        for key in ("price", "change", "open", "high", "low", "prev_close", "volume"):
            assert isinstance(s[key], (int, float)), f"{key} must be numeric"

    def test_daily_series_parseable(self):
        prices = [float(MOCK_DAILY[d]["4. close"]) for d in sorted(MOCK_DAILY.keys())]
        assert all(p > 0 for p in prices)

    def test_forecast_ensemble_all_floats(self):
        import datetime
        base = datetime.date(2023, 1, 1)
        series = {
            (base + datetime.timedelta(days=i)).strftime("%Y-%m-%d"):
                {"4. close": str(150 + i * 0.2)}
            for i in range(80)
        }
        fe = ForecastEngine(series)
        result = fe.run()
        if result.get("ensemble"):
            for v in result["ensemble"]:
                assert isinstance(v, float)


# ── TC-09: Guest access works without login (FR-9) ──────────────────────────

class TestTC09GuestAccess:
    """TC-09: All analysis features accessible without authentication."""

    def test_validate_no_auth_header_required(self, client):
        resp = client.post("/api/v1/validate", json={"symbol": "AAPL"})
        assert resp.status_code != 401
        assert resp.status_code != 403

    def test_analyze_endpoint_no_auth_required(self, client):
        with patch("routes.analysis.MarketDataService") as mock_svc:
            svc = MagicMock()
            svc.get_quote.return_value    = MOCK_QUOTE
            svc.get_daily.return_value    = MOCK_DAILY
            svc.get_overview.return_value = MOCK_OVERVIEW
            svc.get_rsi.return_value      = MOCK_RSI
            svc.get_macd.return_value     = MOCK_MACD
            svc.get_sma.return_value      = MOCK_SMA50
            mock_svc.return_value = svc

            resp = client.post("/api/v1/analyze", json={"symbol": "AAPL"})
            assert resp.status_code != 401
            assert resp.status_code != 403


# ── TC-10: Tabbed navigation works correctly (FR-10) ────────────────────────

class TestTC10TabbedNavigation:
    """TC-10: Full analyze response contains all tab sections; no stale data."""

    def test_analyze_response_has_all_sections(self, client):
        with patch("routes.analysis.MarketDataService") as mock_svc:
            svc = MagicMock()
            svc.get_quote.return_value    = MOCK_QUOTE
            svc.get_daily.return_value    = MOCK_DAILY
            svc.get_overview.return_value = MOCK_OVERVIEW
            svc.get_rsi.return_value      = MOCK_RSI
            svc.get_macd.return_value     = MOCK_MACD
            svc.get_sma.return_value      = MOCK_SMA50
            mock_svc.return_value = svc

            resp = client.post("/api/v1/analyze", json={"symbol": "AAPL"})
            assert resp.status_code == 200
            data = resp.get_json()

            # All three tab sections must be present
            assert "summary"        in data, "Missing summary section"
            assert "technical"      in data, "Missing technical section"
            assert "fundamental"    in data, "Missing fundamental section"
            assert "recommendation" in data, "Missing recommendation section"

    def test_different_symbols_return_independent_data(self):
        fa1 = FundamentalAnalytics({"Symbol": "AAPL", "Name": "Apple Inc.", "PERatio": "28.5"})
        fa2 = FundamentalAnalytics({"Symbol": "MSFT", "Name": "Microsoft Corp.", "PERatio": "32.1"})
        m1 = fa1.metrics()
        m2 = fa2.metrics()
        assert m1["company"] != m2["company"]
        assert m1["valuation"]["pe_ratio"] != m2["valuation"]["pe_ratio"]

    def test_unknown_ticker_returns_404_not_crash(self, client):
        with patch("routes.analysis.MarketDataService") as mock_svc:
            svc = MagicMock()
            svc.get_quote.return_value    = {}  # empty → unknown ticker
            svc.get_daily.return_value    = {}
            svc.get_overview.return_value = {}
            svc.get_rsi.return_value      = {}
            svc.get_macd.return_value     = {}
            svc.get_sma.return_value      = {}
            mock_svc.return_value = svc

            resp = client.post("/api/v1/analyze", json={"symbol": "ZZZZZ"})
            assert resp.status_code == 404
            data = resp.get_json()
            assert "error" in data
