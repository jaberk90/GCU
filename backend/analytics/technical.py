"""
TechnicalAnalytics — FR-5 / US-3
Computes RSI, MACD (calculated locally from price data),
SMA-50, SMA-200, and daily change signals.
MACD is calculated in pure Python — no premium API needed.
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def _latest(series: dict) -> tuple:
    if not series:
        return None, {}
    key = sorted(series.keys())[-1]
    return key, series[key]


def _ema(prices: list[float], period: int) -> list[float]:
    """Exponential moving average over a list of prices."""
    if len(prices) < period:
        return []
    k = 2.0 / (period + 1)
    ema = [sum(prices[:period]) / period]
    for p in prices[period:]:
        ema.append(p * k + ema[-1] * (1 - k))
    return ema


def _calc_macd(daily_series: dict) -> dict | None:
    """
    Calculate MACD(12,26,9) from daily close prices.
    Returns dict with MACD, Signal, Histogram — or None if not enough data.
    """
    if not daily_series:
        return None
    dates  = sorted(daily_series.keys())
    closes = [float(daily_series[d]["4. close"]) for d in dates]

    if len(closes) < 35:  # need at least 26 + a few for signal
        return None

    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)

    # Align: ema26 is shorter, trim ema12 to match
    diff = len(ema12) - len(ema26)
    ema12_aligned = ema12[diff:]

    macd_line = [e12 - e26 for e12, e26 in zip(ema12_aligned, ema26)]

    if len(macd_line) < 9:
        return None

    signal_line = _ema(macd_line, 9)
    # Align signal to macd_line
    sig_diff    = len(macd_line) - len(signal_line)
    macd_trimmed = macd_line[sig_diff:]

    histogram = [m - s for m, s in zip(macd_trimmed, signal_line)]

    return {
        "macd":      round(macd_trimmed[-1], 4),
        "signal":    round(signal_line[-1], 4),
        "histogram": round(histogram[-1], 4),
    }


class TechnicalAnalytics:

    def __init__(self, quote: dict, daily: dict,
                 rsi_series: dict, sma50_series: dict):
        self.quote       = quote
        self.daily       = daily
        self.rsi_series  = rsi_series
        self.sma50_series = sma50_series
        self._signals: list[str] = []

    def _price(self) -> float:
        return float(self.quote.get("05. price", 0))

    def _sma200(self) -> float | None:
        dates = sorted(self.daily.keys())
        if len(dates) < 50:
            return None
        closes = [float(self.daily[d]["4. close"]) for d in dates]
        return round(sum(closes) / len(closes), 2)

    def summary(self) -> dict:
        q = self.quote
        return {
            "price":      float(q.get("05. price",          0)),
            "change":     float(q.get("09. change",         0)),
            "change_pct": q.get("10. change percent",       "0%"),
            "open":       float(q.get("02. open",           0)),
            "high":       float(q.get("03. high",           0)),
            "low":        float(q.get("04. low",            0)),
            "prev_close": float(q.get("08. previous close", 0)),
            "volume":     int(q.get("06. volume",           0)),
        }

    def indicators(self) -> list[dict]:
        price   = self._price()
        results = []
        self._signals = []

        # ── RSI (from API) ──────────────────────────────────────────────────
        _, rsi_point = _latest(self.rsi_series)
        rsi = float(rsi_point["RSI"]) if rsi_point else None
        if rsi is not None:
            if rsi < 30:
                sig, label = "buy",  "Oversold"
            elif rsi > 70:
                sig, label = "sell", "Overbought"
            else:
                sig, label = "hold", "Neutral"
            self._signals.append(sig)
            results.append({
                "name": "RSI (14)", "value": round(rsi, 2),
                "signal": sig, "label": label,
                "description": "Relative Strength Index · <30 oversold, >70 overbought"
            })

        # ── MACD (calculated locally — no premium API) ──────────────────────
        macd_data = _calc_macd(self.daily)
        if macd_data:
            hist  = macd_data["histogram"]
            sig   = "buy"  if hist > 0 else "sell"
            label = "Bullish" if hist > 0 else "Bearish"
            self._signals.append(sig)
            results.append({
                "name": "MACD (12,26,9)", "value": round(hist, 4),
                "macd": macd_data["macd"], "signal_line": macd_data["signal"],
                "signal": sig, "label": label,
                "description": "MACD histogram — calculated from price data"
            })

        # ── SMA 50 (from API) ───────────────────────────────────────────────
        _, sma50_point = _latest(self.sma50_series)
        if sma50_point:
            sma50 = float(sma50_point["SMA"])
            sig   = "buy"       if price > sma50 else "sell"
            label = "Above SMA" if price > sma50 else "Below SMA"
            self._signals.append(sig)
            results.append({
                "name": "SMA 50", "value": round(sma50, 2),
                "signal": sig, "label": label,
                "description": "50-day simple moving average"
            })

        # ── SMA 200 (calculated from compact daily data) ────────────────────
        sma200 = self._sma200()
        if sma200:
            sig   = "buy"       if price > sma200 else "sell"
            label = "Above SMA" if price > sma200 else "Below SMA"
            self._signals.append(sig)
            results.append({
                "name": "SMA 200 (approx)", "value": sma200,
                "signal": sig, "label": label,
                "description": "Approximated from available price history"
            })

        # ── Daily price action ───────────────────────────────────────────────
        change = float(self.quote.get("09. change", 0))
        sig    = "buy"      if change >= 0 else "sell"
        label  = "Up today" if change >= 0 else "Down today"
        self._signals.append(sig)
        results.append({
            "name": "Daily price action", "value": round(change, 2),
            "signal": sig, "label": label,
            "description": "Change vs previous close"
        })

        return results

    def recommendation(self) -> dict:
        if not self._signals:
            self.indicators()

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
