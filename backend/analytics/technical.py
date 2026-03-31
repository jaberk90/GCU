"""
TechnicalAnalytics — FR-5 / US-3
Computes RSI, MACD, SMA-50, SMA-200, daily change signals.
Produces Buy / Hold / Sell recommendation.
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def _latest(series: dict) -> tuple[str | None, dict]:
    if not series:
        return None, {}
    key = sorted(series.keys())[-1]
    return key, series[key]


class TechnicalAnalytics:

    def __init__(self, quote: dict, daily: dict, rsi_series: dict,
                 macd_series: dict, sma50_series: dict):
        self.quote       = quote
        self.daily       = daily
        self.rsi_series  = rsi_series
        self.macd_series = macd_series
        self.sma50_series = sma50_series
        self._signals: list[str] = []

    # ── helpers ────────────────────────────────────────────────────────────────

    def _price(self) -> float:
        return float(self.quote.get("05. price", 0))

    def _sma200(self) -> float | None:
        dates = sorted(self.daily.keys())[-200:]
        if len(dates) < 50:
            return None
        return sum(float(self.daily[d]["4. close"]) for d in dates) / len(dates)

    # ── public ─────────────────────────────────────────────────────────────────

    def summary(self) -> dict:
        q = self.quote
        return {
            "price":      float(q.get("05. price",         0)),
            "change":     float(q.get("09. change",        0)),
            "change_pct": q.get("10. change percent",      "0%"),
            "open":       float(q.get("02. open",          0)),
            "high":       float(q.get("03. high",          0)),
            "low":        float(q.get("04. low",           0)),
            "prev_close": float(q.get("08. previous close",0)),
            "volume":     int(q.get("06. volume",          0)),
        }

    def indicators(self) -> list[dict]:
        price = self._price()
        results = []

        # RSI
        _, rsi_point = _latest(self.rsi_series)
        rsi = float(rsi_point["RSI"]) if rsi_point else None
        if rsi is not None:
            if rsi < 30:
                sig, label = "buy",  "Oversold"
                self._signals.append("buy")
            elif rsi > 70:
                sig, label = "sell", "Overbought"
                self._signals.append("sell")
            else:
                sig, label = "hold", "Neutral"
                self._signals.append("hold")
            results.append({"name": "RSI (14)", "value": round(rsi, 2),
                             "signal": sig, "label": label,
                             "description": "Relative Strength Index · <30 oversold, >70 overbought"})

        # MACD histogram
        _, macd_point = _latest(self.macd_series)
        if macd_point:
            hist  = float(macd_point["MACD_Hist"])
            macd_v = float(macd_point["MACD"])
            sig_v  = float(macd_point["MACD_Signal"])
            sig    = "buy" if hist > 0 else "sell"
            label  = "Bullish" if hist > 0 else "Bearish"
            self._signals.append(sig)
            results.append({"name": "MACD Histogram", "value": round(hist, 4),
                             "macd": round(macd_v, 4), "signal_line": round(sig_v, 4),
                             "signal": sig, "label": label,
                             "description": "Moving Average Convergence Divergence"})

        # SMA 50
        _, sma50_point = _latest(self.sma50_series)
        if sma50_point:
            sma50 = float(sma50_point["SMA"])
            sig   = "buy" if price > sma50 else "sell"
            label = "Above SMA" if price > sma50 else "Below SMA"
            self._signals.append(sig)
            results.append({"name": "SMA 50", "value": round(sma50, 2),
                             "signal": sig, "label": label,
                             "description": "50-day simple moving average"})

        # SMA 200
        sma200 = self._sma200()
        if sma200:
            sig   = "buy" if price > sma200 else "sell"
            label = "Above SMA" if price > sma200 else "Below SMA"
            self._signals.append(sig)
            results.append({"name": "SMA 200", "value": round(sma200, 2),
                             "signal": sig, "label": label,
                             "description": "200-day simple moving average (approx.)"})

        # Daily price action
        change = float(self.quote.get("09. change", 0))
        sig    = "buy" if change >= 0 else "sell"
        label  = "Up today" if change >= 0 else "Down today"
        self._signals.append(sig)
        results.append({"name": "Daily price action", "value": round(change, 2),
                        "signal": sig, "label": label,
                        "description": "Change vs previous close"})

        return results

    def recommendation(self) -> dict:
        if not self._signals:
            self.indicators()  # ensure signals are populated

        total = len(self._signals)
        buys  = self._signals.count("buy")
        sells = self._signals.count("sell")
        holds = self._signals.count("hold")

        buy_pct  = buys  / total if total else 0
        sell_pct = sells / total if total else 0

        if buy_pct >= 0.6:
            action = "BUY"
            reason = f"{buys} of {total} indicators signal bullish conditions."
        elif sell_pct >= 0.6:
            action = "SELL"
            reason = f"{sells} of {total} indicators signal bearish conditions."
        else:
            action = "HOLD"
            reason = f"Mixed signals across {total} indicators. Monitor closely."

        return {
            "action":     action,
            "reason":     reason,
            "buy_count":  buys,
            "sell_count": sells,
            "hold_count": holds,
            "total":      total
        }
