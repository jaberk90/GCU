"""
ForecastEngine — FR-6 / US-6
Runs ARIMA and LSTM models on historical price data.
Returns: forecast series, confidence score, direction (Up/Down/Neutral).
Fails safely when input data is insufficient.
"""

from __future__ import annotations
import logging
import numpy as np

logger = logging.getLogger(__name__)

MIN_HISTORY_ARIMA = 30
MIN_HISTORY_LSTM  = 60
FORECAST_DAYS     = 10


class ForecastEngine:

    def __init__(self, daily_series: dict):
        dates  = sorted(daily_series.keys())
        self.dates  = dates
        self.closes = [float(daily_series[d]["4. close"]) for d in dates]

    # ── ARIMA ──────────────────────────────────────────────────────────────────

    def _arima_forecast(self) -> list[float] | None:
        if len(self.closes) < MIN_HISTORY_ARIMA:
            logger.warning("Insufficient data for ARIMA (%d rows)", len(self.closes))
            return None
        try:
            from statsmodels.tsa.arima.model import ARIMA
            model  = ARIMA(self.closes, order=(5, 1, 0))
            result = model.fit()
            fc     = result.forecast(steps=FORECAST_DAYS)
            return [round(float(v), 2) for v in fc]
        except Exception as e:
            logger.error("ARIMA failed: %s", e)
            return None

    # ── LSTM ───────────────────────────────────────────────────────────────────

    def _lstm_forecast(self) -> list[float] | None:
        if len(self.closes) < MIN_HISTORY_LSTM:
            logger.warning("Insufficient data for LSTM (%d rows)", len(self.closes))
            return None
        try:
            import tensorflow as tf
            from tensorflow.keras.models import Sequential
            from tensorflow.keras.layers import LSTM, Dense

            data   = np.array(self.closes, dtype=np.float32)
            mn, mx = data.min(), data.max()
            norm   = (data - mn) / (mx - mn + 1e-8)

            look_back = 20
            X, y = [], []
            for i in range(look_back, len(norm)):
                X.append(norm[i - look_back:i])
                y.append(norm[i])
            X = np.array(X).reshape(-1, look_back, 1)
            y = np.array(y)

            model = Sequential([
                LSTM(32, input_shape=(look_back, 1)),
                Dense(1)
            ])
            model.compile(optimizer="adam", loss="mse")
            model.fit(X, y, epochs=10, batch_size=16, verbose=0)

            last_seq = norm[-look_back:].reshape(1, look_back, 1)
            preds = []
            for _ in range(FORECAST_DAYS):
                p = float(model.predict(last_seq, verbose=0)[0][0])
                preds.append(p)
                last_seq = np.append(last_seq[0, 1:, 0], p).reshape(1, look_back, 1)

            # Denormalise
            denorm = [round(float(p * (mx - mn) + mn), 2) for p in preds]
            return denorm
        except Exception as e:
            logger.error("LSTM failed: %s", e)
            return None

    # ── Main entry ─────────────────────────────────────────────────────────────

    def run(self) -> dict:
        arima_fc = self._arima_forecast()
        lstm_fc  = self._lstm_forecast()

        current_price = self.closes[-1]

        # Ensemble: average available models
        available = [fc for fc in [arima_fc, lstm_fc] if fc]
        if not available:
            return {
                "error":      "Insufficient historical data to generate a forecast.",
                "arima":      None,
                "lstm":       None,
                "ensemble":   None,
                "confidence": 0.0,
                "direction":  "Neutral",
            }

        ensemble = [round(sum(fc[i] for fc in available) / len(available), 2)
                    for i in range(FORECAST_DAYS)]

        final_price = ensemble[-1]
        pct_change  = (final_price - current_price) / (current_price + 1e-8) * 100

        # Confidence: higher when both models agree in direction
        if len(available) == 2:
            both_up   = arima_fc[-1] > current_price and lstm_fc[-1] > current_price
            both_down = arima_fc[-1] < current_price and lstm_fc[-1] < current_price
            confidence = 0.80 if (both_up or both_down) else 0.55
        else:
            confidence = 0.60  # single model

        if pct_change > 1.5:
            direction = "Up"
        elif pct_change < -1.5:
            direction = "Down"
        else:
            direction = "Neutral"

        # Forecast date labels
        import datetime
        today = datetime.date.today()
        labels = [(today + datetime.timedelta(days=i+1)).strftime("%b %d")
                  for i in range(FORECAST_DAYS)]

        return {
            "current_price": round(current_price, 2),
            "arima":         arima_fc,
            "lstm":          lstm_fc,
            "ensemble":      ensemble,
            "labels":        labels,
            "confidence":    round(confidence, 2),
            "direction":     direction,
            "pct_change":    round(pct_change, 2),
            "models_used":   ("ARIMA + LSTM" if len(available) == 2 else
                              "ARIMA" if arima_fc else "LSTM"),
        }
