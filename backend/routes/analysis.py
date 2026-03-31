"""
Route: /api/v1/analyze
FR-1, FR-4, FR-5, FR-10 — Full analysis: summary, technical, fundamental
"""

from flask import Blueprint, request, jsonify
from services.market_data import MarketDataService
from analytics.technical import TechnicalAnalytics
from analytics.fundamental import FundamentalAnalytics
import logging

analysis_bp = Blueprint("analysis", __name__)
logger = logging.getLogger(__name__)


@analysis_bp.route("/analyze", methods=["POST"])
def analyze():
    """
    POST /api/v1/analyze
    Body: { "symbol": "AAPL" }
    Returns full technical + fundamental analysis result
    """
    data = request.get_json(silent=True) or {}
    symbol = str(data.get("symbol", "")).strip().upper()

    if not symbol:
        return jsonify({"error": "Symbol is required."}), 400

    logger.info("Analysis requested for: %s", symbol)

    try:
        svc = MarketDataService()

        quote        = svc.get_quote(symbol)
        daily        = svc.get_daily(symbol)
        overview     = svc.get_overview(symbol)
        rsi_data     = svc.get_rsi(symbol)
        macd_data    = svc.get_macd(symbol)
        sma50_data   = svc.get_sma(symbol, 50)

        if not quote:
            logger.warning("No data returned for symbol: %s", symbol)
            return jsonify({"error": f"No market data found for '{symbol}'. Verify the ticker and try again."}), 404

        tech   = TechnicalAnalytics(quote, daily, rsi_data, macd_data, sma50_data)
        fund   = FundamentalAnalytics(overview)

        result = {
            "symbol":      symbol,
            "summary":     tech.summary(),
            "technical":   tech.indicators(),
            "fundamental": fund.metrics(),
            "recommendation": tech.recommendation()
        }

        logger.info("Analysis complete for %s — recommendation: %s", symbol, result["recommendation"]["action"])
        return jsonify(result)

    except Exception as exc:
        logger.error("Analysis failed for %s: %s", symbol, str(exc))
        return jsonify({"error": "Analysis service encountered an error. Please try again."}), 500
