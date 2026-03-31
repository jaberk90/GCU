"""
Route: /api/v1/predict
FR-6 — Forecast: ARIMA + LSTM using 6 months of daily data from yfinance.
"""

from flask import Blueprint, request, jsonify
from services.market_data import MarketDataService
from analytics.forecast import ForecastEngine
import logging

predict_bp = Blueprint("predict", __name__)
logger = logging.getLogger(__name__)


@predict_bp.route("/predict", methods=["POST"])
def predict():
    data   = request.get_json(silent=True) or {}
    symbol = str(data.get("symbol", "")).strip().upper()

    if not symbol:
        return jsonify({"error": "Symbol is required."}), 400

    logger.info("Prediction requested for: %s", symbol)

    try:
        svc   = MarketDataService(symbol)
        daily = svc.get_daily()

        if not daily:
            return jsonify({
                "error": f"No historical data available for '{symbol}'."
            }), 404

        engine = ForecastEngine(daily)
        result = engine.run()

        logger.info("Prediction complete for %s — direction: %s",
                    symbol, result.get("direction"))
        return jsonify({"symbol": symbol, **result})

    except Exception as exc:
        logger.error("Prediction failed for %s: %s", symbol, str(exc))
        return jsonify({
            "error": "Prediction model encountered an error."
        }), 500
