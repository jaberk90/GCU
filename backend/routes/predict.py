"""
Route: /api/v1/predict
FR-6 — Forecast view: ARIMA + LSTM models, confidence score, recommendation
"""

from flask import Blueprint, request, jsonify
from services.market_data import MarketDataService
from analytics.forecast import ForecastEngine
import logging

predict_bp = Blueprint("predict", __name__)
logger = logging.getLogger(__name__)


@predict_bp.route("/predict", methods=["POST"])
def predict():
    """
    POST /api/v1/predict
    Body: { "symbol": "AAPL" }
    Returns forecast series + confidence score + direction
    """
    data = request.get_json(silent=True) or {}
    symbol = str(data.get("symbol", "")).strip().upper()

    if not symbol:
        return jsonify({"error": "Symbol is required."}), 400

    logger.info("Prediction requested for: %s", symbol)

    try:
        svc   = MarketDataService()
        daily = svc.get_daily(symbol, outputsize="full")

        if not daily:
            return jsonify({"error": f"No historical data available for '{symbol}'."}), 404

        engine = ForecastEngine(daily)
        result = engine.run()  # returns arima + lstm forecasts + confidence + direction

        logger.info("Prediction complete for %s — direction: %s, confidence: %.2f",
                    symbol, result["direction"], result["confidence"])
        return jsonify({"symbol": symbol, **result})

    except Exception as exc:
        logger.error("Prediction failed for %s: %s", symbol, str(exc))
        return jsonify({"error": "Prediction model encountered an error. Limited data may be the cause."}), 500
