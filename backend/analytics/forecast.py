"""
ForecastEngine — FR-6 / US-6
Pure NumPy implementations of ARIMA(5,1,0) and LSTM.
Zero Fortran/C++ build dependencies — deploys on any platform
including Render ARM64 free tier.
"""

from __future__ import annotations
import logging
import datetime
import numpy as np

logger = logging.getLogger(__name__)

MIN_HISTORY_ARIMA = 30
MIN_HISTORY_LSTM  = 60
FORECAST_DAYS     = 10


# ══════════════════════════════════════════════════════════════════════════════
# Pure-NumPy ARIMA(p,d,0)
# ══════════════════════════════════════════════════════════════════════════════

class _PureARIMA:
    """
    ARIMA(p, d, 0) via OLS on differenced series.
    No statsmodels / scipy required.
    """

    def __init__(self, p: int = 5, d: int = 1):
        self.p = p
        self.d = d
        self.coef_: np.ndarray | None = None
        self.intercept_: float = 0.0
        self._undiff_anchor: float = 0.0

    def _difference(self, x: np.ndarray, d: int) -> np.ndarray:
        for _ in range(d):
            x = np.diff(x)
        return x

    def fit(self, series: np.ndarray) -> "_PureARIMA":
        self._orig = series.copy()
        y = self._difference(series, self.d)
        n = len(y)
        if n <= self.p:
            raise ValueError("Series too short for AR order.")

        X_rows, y_rows = [], []
        for i in range(self.p, n):
            X_rows.append(y[i - self.p:i][::-1])
            y_rows.append(y[i])

        X = np.column_stack([np.ones(len(X_rows)), np.array(X_rows)])
        Y = np.array(y_rows)

        ridge = 1e-6 * np.eye(X.shape[1])
        try:
            beta = np.linalg.solve(X.T @ X + ridge, X.T @ Y)
        except np.linalg.LinAlgError:
            beta = np.zeros(X.shape[1])

        self.intercept_ = beta[0]
        self.coef_       = beta[1:]
        self._diff_tail  = y[-(self.p):]
        return self

    def forecast(self, steps: int) -> np.ndarray:
        if self.coef_ is None:
            raise RuntimeError("Call fit() first.")

        history = list(self._diff_tail)
        preds_diff = []
        for _ in range(steps):
            lags = np.array(history[-self.p:][::-1])
            val  = self.intercept_ + float(self.coef_ @ lags)
            preds_diff.append(val)
            history.append(val)

        result = np.array(preds_diff)
        for i in range(self.d):
            anchor = self._orig[-1] if i == 0 else self._undiff_anchor
            result = np.cumsum(result) + anchor
            self._undiff_anchor = float(result[-1])

        return result


# ══════════════════════════════════════════════════════════════════════════════
# Pure-NumPy LSTM
# ══════════════════════════════════════════════════════════════════════════════

def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -500, 500)))


class _NumpyLSTM:
    """
    Single-layer LSTM + linear output, pure NumPy.
    """

    def __init__(self, look_back: int = 20, hidden: int = 16,
                 epochs: int = 25, lr: float = 0.003):
        self.look_back = look_back
        self.hidden    = hidden
        self.epochs    = epochs
        self.lr        = lr
        np.random.seed(42)
        s = 0.08
        self.Wh = np.random.randn(1 + hidden, 4 * hidden) * s
        self.bh = np.zeros(4 * hidden)
        self.Wy = np.random.randn(hidden, 1) * s
        self.by = np.zeros(1)

    def _step(self, x_t: float, h: np.ndarray, c: np.ndarray):
        z  = np.dot(np.append([x_t], h), self.Wh) + self.bh
        hs = self.hidden
        i  = _sigmoid(z[0*hs:1*hs])
        f  = _sigmoid(z[1*hs:2*hs])
        g  = np.tanh(z[2*hs:3*hs])
        o  = _sigmoid(z[3*hs:4*hs])
        c  = f * c + i * g
        h  = o * np.tanh(c)
        return h, c

    def _forward(self, seq: np.ndarray):
        h = np.zeros(self.hidden)
        c = np.zeros(self.hidden)
        for x_t in seq:
            h, c = self._step(float(x_t), h, c)
        return h, c

    def _predict_val(self, seq: np.ndarray) -> float:
        h, _ = self._forward(seq)
        return float(h @ self.Wy + self.by)

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        for _ in range(self.epochs):
            for idx in np.random.permutation(len(X)):
                pred    = self._predict_val(X[idx])
                err     = pred - float(y[idx])
                h_last, _ = self._forward(X[idx])
                dWy     = np.outer(h_last, [err])
                self.Wy -= self.lr * np.clip(dWy, -1, 1)
                self.by -= self.lr * np.clip([err], -1, 1)
                d_h     = (self.Wy @ [[err]]).flatten()
                xh      = np.append([X[idx, -1]], h_last)
                dWh     = np.outer(xh, np.tile(d_h, 4))
                self.Wh -= self.lr * np.clip(dWh, -1, 1)
                self.bh -= self.lr * np.clip(np.tile(d_h, 4), -1, 1)

    def predict_steps(self, seed_seq: np.ndarray, steps: int) -> list[float]:
        seq = seed_seq.copy()
        out = []
        for _ in range(steps):
            p = self._predict_val(seq)
            out.append(p)
            seq = np.append(seq[1:], p)
        return out


# ══════════════════════════════════════════════════════════════════════════════
# ForecastEngine — public interface
# ══════════════════════════════════════════════════════════════════════════════

class ForecastEngine:

    def __init__(self, daily_series: dict):
        dates       = sorted(daily_series.keys())
        self.closes = np.array([float(daily_series[d]["4. close"]) for d in dates])

    def _arima_forecast(self) -> list[float] | None:
        if len(self.closes) < MIN_HISTORY_ARIMA:
            return None
        try:
            model = _PureARIMA(p=5, d=1).fit(self.closes)
            fc    = model.forecast(FORECAST_DAYS)
            last  = self.closes[-1]
            fc    = np.clip(fc, last * 0.80, last * 1.20)
            return [round(float(v), 2) for v in fc]
        except Exception as e:
            logger.error("ARIMA failed: %s", e)
            return None

    def _lstm_forecast(self) -> list[float] | None:
        if len(self.closes) < MIN_HISTORY_LSTM:
            return None
        try:
            mn, mx = self.closes.min(), self.closes.max()
            norm   = (self.closes - mn) / (mx - mn + 1e-8)
            look_back = 20
            X = np.array([norm[i - look_back:i] for i in range(look_back, len(norm))])
            y = norm[look_back:]
            model = _NumpyLSTM(look_back=look_back, hidden=16, epochs=25, lr=0.003)
            model.fit(X, y)
            raw  = model.predict_steps(norm[-look_back:], FORECAST_DAYS)
            last = float(self.closes[-1])
            out  = []
            for p in raw:
                val = float(p) * (mx - mn) + mn
                val = max(last * 0.85, min(last * 1.15, val))
                out.append(round(val, 2))
            return out
        except Exception as e:
            logger.error("LSTM failed: %s", e)
            return None

    def run(self) -> dict:
        arima_fc = self._arima_forecast()
        lstm_fc  = self._lstm_forecast()
        current  = float(self.closes[-1])
        available = [fc for fc in [arima_fc, lstm_fc] if fc]

        if not available:
            return {
                "error": "Insufficient historical data to generate a forecast.",
                "arima": None, "lstm": None, "ensemble": None,
                "confidence": 0.0, "direction": "Neutral",
            }

        ensemble = [
            round(sum(fc[i] for fc in available) / len(available), 2)
            for i in range(FORECAST_DAYS)
        ]
        pct_change = (ensemble[-1] - current) / (current + 1e-8) * 100

        if len(available) == 2:
            both_up   = arima_fc[-1] > current and lstm_fc[-1] > current
            both_down = arima_fc[-1] < current and lstm_fc[-1] < current
            confidence = 0.80 if (both_up or both_down) else 0.55
        else:
            confidence = 0.60

        direction = ("Up" if pct_change > 1.5 else
                     "Down" if pct_change < -1.5 else "Neutral")

        today  = datetime.date.today()
        labels = [(today + datetime.timedelta(days=i + 1)).strftime("%b %d")
                  for i in range(FORECAST_DAYS)]

        return {
            "current_price": round(current, 2),
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
