"""
ForecastEngine — FR-6 / US-6
Runs ARIMA and LSTM models on historical price data.
Returns: forecast series, confidence score, direction (Up/Down/Neutral).
Fails safely when input data is insufficient.

LSTM implementation uses pure NumPy — no TensorFlow/Keras dependency —
so it deploys on any platform including Render's ARM64 free tier.
"""

from __future__ import annotations
import logging
import numpy as np

logger = logging.getLogger(__name__)

MIN_HISTORY_ARIMA = 30
MIN_HISTORY_LSTM  = 60
FORECAST_DAYS     = 10


# ── Pure-NumPy LSTM helpers ────────────────────────────────────────────────────

def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -500, 500)))

def _tanh(x: np.ndarray) -> np.ndarray:
    return np.tanh(x)


class _LSTMCell:
    """Single-layer LSTM cell with one hidden unit group, pure NumPy."""

    def __init__(self, input_size: int, hidden_size: int):
        scale = 0.1
        # Weight matrices [input+hidden → 4*hidden] (i, f, g, o gates)
        self.W = np.random.randn(input_size + hidden_size, 4 * hidden_size) * scale
        self.b = np.zeros(4 * hidden_size)
        self.hidden_size = hidden_size

    def forward_sequence(self, X: np.ndarray) -> np.ndarray:
        """X: (seq_len, input_size) → outputs: (seq_len, hidden_size)"""
        h = np.zeros(self.hidden_size)
        c = np.zeros(self.hidden_size)
        outputs = []
        for t in range(len(X)):
            combined = np.concatenate([X[t], h])
            gates    = combined @ self.W + self.b
            hs = self.hidden_size
            i  = _sigmoid(gates[0*hs:1*hs])
            f  = _sigmoid(gates[1*hs:2*hs])
            g  = _tanh   (gates[2*hs:3*hs])
            o  = _sigmoid(gates[3*hs:4*hs])
            c  = f * c + i * g
            h  = o * _tanh(c)
            outputs.append(h.copy())
        return np.array(outputs)

    def update_weights(self, dW: np.ndarray, db: np.ndarray, lr: float) -> None:
        self.W -= lr * np.clip(dW, -1.0, 1.0)
        self.b -= lr * np.clip(db, -1.0, 1.0)


class _NumpyLSTMModel:
    """
    Minimal one-layer LSTM + linear output, trained with truncated BPTT.
    Lightweight, platform-agnostic, no heavy dependencies.
    """

    def __init__(self, look_back: int = 20, hidden_size: int = 16,
                 epochs: int = 30, lr: float = 0.005):
        self.look_back   = look_back
        self.hidden_size = hidden_size
        self.epochs      = epochs
        self.lr          = lr
        np.random.seed(42)
        self.lstm   = _LSTMCell(1, hidden_size)
        self.W_out  = np.random.randn(hidden_size, 1) * 0.1
        self.b_out  = np.zeros(1)

    def _predict_one(self, seq: np.ndarray) -> float:
        out = self.lstm.forward_sequence(seq.reshape(-1, 1))
        return float(out[-1] @ self.W_out + self.b_out)

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        for epoch in range(self.epochs):
            total_loss = 0.0
            for i in range(len(X)):
                pred  = self._predict_one(X[i])
                err   = pred - float(y[i])
                total_loss += err ** 2
                # Gradient w.r.t. output layer
                d_out   = np.array([[err]])
                dW_out  = self.lstm.forward_sequence(X[i].reshape(-1, 1))[-1:].T @ d_out
                db_out  = d_out[0]
                self.W_out -= self.lr * np.clip(dW_out, -1.0, 1.0)
                self.b_out -= self.lr * np.clip(db_out, -1.0, 1.0)
                # Simplified gradient pass into LSTM weights (one-step approx)
                d_h   = (d_out @ self.W_out.T)[0]
                h_val = self.lstm.forward_sequence(X[i].reshape(-1, 1))[-1]
                # Approximate LSTM weight gradient via outer product
                last_x    = np.concatenate([X[i, -1:], h_val])
                dW_lstm   = np.outer(last_x, np.tile(d_h, 4))
                db_lstm   = np.tile(d_h, 4)
                self.lstm.update_weights(dW_lstm, db_lstm, self.lr)
            if epoch % 10 == 0:
                logger.debug("LSTM epoch %d  loss=%.6f", epoch, total_loss / len(X))

    def predict_steps(self, last_seq: np.ndarray, steps: int) -> list[float]:
        seq = last_seq.copy()
        preds = []
        for _ in range(steps):
            p = self._predict_one(seq)
            preds.append(p)
            seq = np.append(seq[1:], p)
        return preds


class ForecastEngine:

    def __init__(self, daily_series: dict):
        dates       = sorted(daily_series.keys())
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

    # ── LSTM (pure NumPy — no TensorFlow) ──────────────────────────────────────

    def _lstm_forecast(self) -> list[float] | None:
        if len(self.closes) < MIN_HISTORY_LSTM:
            logger.warning("Insufficient data for LSTM (%d rows)", len(self.closes))
            return None
        try:
            data = np.array(self.closes, dtype=np.float64)
            mn, mx = data.min(), data.max()
            norm   = (data - mn) / (mx - mn + 1e-8)

            look_back = 20
            X, y = [], []
            for i in range(look_back, len(norm)):
                X.append(norm[i - look_back:i])
                y.append(norm[i])
            X = np.array(X)
            y = np.array(y)

            model = _NumpyLSTMModel(look_back=look_back, hidden_size=16,
                                    epochs=30, lr=0.005)
            model.fit(X, y)

            last_seq = norm[-look_back:]
            raw_preds = model.predict_steps(last_seq, FORECAST_DAYS)

            # Denormalise and clamp to ±15% of current price
            current = self.closes[-1]
            denorm  = []
            for p in raw_preds:
                val = float(p) * (mx - mn) + mn
                val = max(current * 0.85, min(current * 1.15, val))
                denorm.append(round(val, 2))
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
