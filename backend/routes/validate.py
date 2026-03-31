"""
Route: /api/v1/validate
FR-2, FR-3 — Validate ticker symbol input before analysis
"""

from flask import Blueprint, request, jsonify
import re
import logging

validate_bp = Blueprint("validate", __name__)
logger = logging.getLogger(__name__)

TICKER_PATTERN = re.compile(r'^[A-Z]{1,10}$')

@validate_bp.route("/validate", methods=["POST"])
def validate_ticker():
    """
    POST /api/v1/validate
    Body: { "symbol": "AAPL" }
    Returns: { "valid": true/false, "message": "..." }
    """
    data = request.get_json(silent=True) or {}
    symbol = str(data.get("symbol", "")).strip().upper()

    logger.info("Validation request for symbol: %s", symbol or "(empty)")

    if not symbol:
        return jsonify({"valid": False, "message": "Stock symbol is required."}), 400

    if not TICKER_PATTERN.match(symbol):
        logger.warning("Invalid symbol format: %s", symbol)
        return jsonify({"valid": False, "message": f"'{symbol}' is not a valid ticker format. Use 1–10 letters only."}), 400

    return jsonify({"valid": True, "symbol": symbol, "message": "Symbol format is valid."})
