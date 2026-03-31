"""
Route: /api/v1/analyze
FR-1, FR-4, FR-5 — Full analysis: summary, technical, fundamental.
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
    data   = request.get_json(silent=True) or {}
    symbol = str(data.get("symbol", "")).strip().upper()

    if not symbol:
        return jsonify({"error": "Symbol is required."}), 400

    logger.info("Analysis requested for: %s", symbol)

    try:
        svc     = MarketDataService()
        fetched = svc.fetch_all(symbol)   # parallel fetch

        quote    = fetched["quote"]
        daily    = fetched["daily"]
        overview = fetched["overview"]
        rsi      = fetched["rsi"]
        sma50    = fetched["sma50"]

        if not quote or not quote.get("05. price"):
            logger.warning("No quote data for: %s", symbol)
            return jsonify({
                "error": f"No market data found for '{symbol}'. "
                         f"Please verify the ticker symbol and try again."
            }), 404

        tech = TechnicalAnalytics(quote, daily, rsi, sma50)
        fund = FundamentalAnalytics(overview)

        result = {
            "symbol":         symbol,
            "summary":        tech.summary(),
            "technical":      tech.indicators(),
            "fundamental":    fund.metrics(),
            "recommendation": tech.recommendation(),
        }

        logger.info("Analysis complete for %s — %s",
                    symbol, result["recommendation"]["action"])
        return jsonify(result)

    except Exception as exc:
        logger.error("Analysis failed for %s: %s", symbol, str(exc))
        return jsonify({"error": "Analysis service encountered an error. Please try again."}), 500
