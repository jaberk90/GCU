"""
ForecastEngine — FR-6 / US-6
ARIMA(2,1,0) + linear trend regression (last 60 days only).
Pure NumPy — runs in milliseconds on Render free tier.
"""

from __future__ import annotations
import datetime
import logging
import numpy as np

logger = logging.getLogger(__name__)
FORECAST_DAYS  = 10
MIN_HISTORY    = 30
TREND_WINDOW   = 60   # only use recent 60 days for trend — avoids stale history bias


class ForecastEngine:

    def __init__(self, daily_series: dict):
        dates       = sorted(daily_series.keys())
        self.closes = np.array([float(daily_series[d]["4. close"]) for d in dates])

    def _arima_forecast(self) -> list[float] | None:
        if len(self.closes) < MIN_HISTORY:
            return None
        try:
            diff = np.diff(self.closes)
            p    = 2
            n    = len(diff)
            if n <= p:
                return None
            X = np.column_stack([
                np.ones(n - p),
                *[diff[p - j - 1:n - j - 1] for j in range(p)]
            ])
            Y     = diff[p:]
            ridge = 1e-6 * np.eye(X.shape[1])
            beta  = np.linalg.solve(X.T @ X + ridge, X.T @ Y)
            hist  = list(diff[-(p):])
            preds = []
            cur   = float(self.closes[-1])
            last  = cur
            for _ in range(FORECAST_DAYS):
                lags = np.array(hist[-p:][::-1])
                d    = beta[0] + float(beta[1:] @ lags)
                cur  = cur + d
                cur  = max(last * 0.85, min(last * 1.15, cur))
                preds.append(round(cur, 2))
                hist.append(d)
            return preds
        except Exception as e:
            logger.error("ARIMA failed: %s", e)
            return None

    def _trend_forecast(self) -> list[float] | None:
        # Use only the most recent TREND_WINDOW days to avoid stale history bias
        closes = self.closes[-TREND_WINDOW:] if len(self.closes) >= TREND_WINDOW else self.closes
        if len(closes) < MIN_HISTORY:
            return None
        try:
            x     = np.arange(len(closes), dtype=float)
            xm, ym = x.mean(), closes.mean()
            denom = np.sum((x - xm) ** 2)
            if denom == 0:
                return None
            slope = np.sum((x - xm) * (closes - ym)) / denom
            inter = ym - slope * xm
            last  = float(closes[-1])
            preds = [slope * (len(closes) + i) + inter for i in range(FORECAST_DAYS)]
            # Tighter clamp — ±10% max from current price
            preds = np.clip(preds, last * 0.90, last * 1.10)
            return [round(float(p), 2) for p in preds]
        except Exception as e:
            logger.error("Trend failed: %s", e)
            return None

    def run(self) -> dict:
        arima_fc = self._arima_forecast()
        trend_fc = self._trend_forecast()
        current  = float(self.closes[-1])
        available = [fc for fc in [arima_fc, trend_fc] if fc]

        if not available:
            return {
                "error": "Insufficient historical data.",
                "arima": None, "lstm": None, "ensemble": None,
                "confidence": 0.0, "direction": "Neutral",
            }

        ensemble = [
            round(sum(fc[i] for fc in available) / len(available), 2)
            for i in range(FORECAST_DAYS)
        ]
        pct_change = (ensemble[-1] - current) / (current + 1e-8) * 100

        if len(available) == 2:
            both_up   = arima_fc[-1] > current and trend_fc[-1] > current
            both_down = arima_fc[-1] < current and trend_fc[-1] < current
            confidence = 0.80 if (both_up or both_down) else 0.55
        else:
            confidence = 0.60

        direction = ("Up"   if pct_change >  1.5 else
                     "Down" if pct_change < -1.5 else "Neutral")

        today  = datetime.date.today()
        labels = [(today + datetime.timedelta(days=i + 1)).strftime("%b %d")
                  for i in range(FORECAST_DAYS)]

        return {
            "current_price": round(current, 2),
            "arima":         arima_fc,
            "lstm":          trend_fc,
            "ensemble":      ensemble,
            "labels":        labels,
            "confidence":    round(confidence, 2),
            "direction":     direction,
            "pct_change":    round(pct_change, 2),
            "models_used":   "ARIMA + Trend Regression",
        }
