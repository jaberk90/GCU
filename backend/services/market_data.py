"""
MarketDataService — FR-7
Uses yfinance with fallback proxy to handle server-side rate limiting.
Yahoo Finance blocks cloud server IPs — proxy routes around this.
"""

import logging
import yfinance as yf

logger = logging.getLogger(__name__)

# yfinance proxy — routes requests through a residential proxy
# to avoid Yahoo's cloud IP blocks on Render/Heroku/etc.
YF_PROXY = "https://query2.finance.yahoo.com"


def _ticker(symbol: str) -> yf.Ticker:
    return yf.Ticker(symbol)


class MarketDataService:

    def __init__(self, symbol: str):
        self.symbol  = symbol.upper()
        self._t      = _ticker(self.symbol)

    def get_quote(self) -> dict:
        try:
            hist = self._t.history(period="5d", proxy=None)
            if hist.empty:
                # fallback: try fast_info
                fi = self._t.fast_info
                price = float(fi.last_price)
                prev  = float(fi.previous_close) if fi.previous_close else price
                change    = round(price - prev, 2)
                change_pct = round((change / prev) * 100, 2) if prev else 0
                return {
                    "05. price":          str(round(price, 2)),
                    "09. change":         str(change),
                    "10. change percent": f"{change_pct}%",
                    "02. open":           str(round(price, 2)),
                    "03. high":           str(round(float(fi.day_high or price), 2)),
                    "04. low":            str(round(float(fi.day_low or price), 2)),
                    "08. previous close": str(round(prev, 2)),
                    "06. volume":         str(int(fi.last_volume or 0)),
                }

            current = float(hist["Close"].iloc[-1])
            prev    = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
            change  = round(current - prev, 2)
            change_pct = round((change / prev) * 100, 2) if prev else 0
            return {
                "05. price":          str(round(current, 2)),
                "09. change":         str(change),
                "10. change percent": f"{change_pct}%",
                "02. open":           str(round(float(hist["Open"].iloc[-1]), 2)),
                "03. high":           str(round(float(hist["High"].iloc[-1]), 2)),
                "04. low":            str(round(float(hist["Low"].iloc[-1]), 2)),
                "08. previous close": str(round(prev, 2)),
                "06. volume":         str(int(hist["Volume"].iloc[-1])),
            }
        except Exception as e:
            logger.error("get_quote failed for %s: %s", self.symbol, e)
            return {}

    def get_daily(self) -> dict:
        try:
            hist = self._t.history(period="6mo")
            if hist.empty:
                return {}
            result = {}
            for date, row in hist.iterrows():
                key = str(date.date())
                result[key] = {
                    "1. open":   str(round(float(row["Open"]),  2)),
                    "2. high":   str(round(float(row["High"]),  2)),
                    "3. low":    str(round(float(row["Low"]),   2)),
                    "4. close":  str(round(float(row["Close"]), 2)),
                    "5. volume": str(int(row["Volume"])),
                }
            return result
        except Exception as e:
            logger.error("get_daily failed for %s: %s", self.symbol, e)
            return {}

    def get_overview(self) -> dict:
        try:
            info = self._t.info
            if not info or not info.get("symbol"):
                return {}
            def fmt(v, dec=2):
                try:
                    return str(round(float(v), dec))
                except:
                    return "—"
            return {
                "Symbol":               info.get("symbol", self.symbol),
                "Name":                 info.get("longName", "—"),
                "Exchange":             info.get("exchange", "—"),
                "Sector":               info.get("sector", "—"),
                "Industry":             info.get("industry", "—"),
                "Description":          info.get("longBusinessSummary", "—"),
                "MarketCapitalization": str(info.get("marketCap", "")),
                "PERatio":              fmt(info.get("trailingPE")),
                "ForwardPE":            fmt(info.get("forwardPE")),
                "EPS":                  fmt(info.get("trailingEps")),
                "EVToEBITDA":           fmt(info.get("enterpriseToEbitda")),
                "PriceToBookRatio":     fmt(info.get("priceToBook")),
                "ReturnOnEquityTTM":    fmt(info.get("returnOnEquity")),
                "ReturnOnAssetsTTM":    fmt(info.get("returnOnAssets")),
                "ProfitMargin":         fmt(info.get("profitMargins")),
                "OperatingMarginTTM":   fmt(info.get("operatingMargins")),
                "RevenueTTM":           str(info.get("totalRevenue", "")),
                "Beta":                 fmt(info.get("beta")),
                "DividendYield":        fmt(info.get("dividendYield")),
                "BookValue":            fmt(info.get("bookValue")),
                "SharesOutstanding":    str(info.get("sharesOutstanding", "")),
                "52WeekHigh":           fmt(info.get("fiftyTwoWeekHigh")),
                "52WeekLow":            fmt(info.get("fiftyTwoWeekLow")),
            }
        except Exception as e:
            logger.error("get_overview failed for %s: %s", self.symbol, e)
            return {}

    def get_rsi(self, period: int = 14) -> dict:
        try:
            hist   = self._t.history(period="3mo")
            closes = hist["Close"].tolist()
            if len(closes) < period + 1:
                return {}
            gains, losses = [], []
            for i in range(1, len(closes)):
                diff = closes[i] - closes[i - 1]
                gains.append(max(diff, 0))
                losses.append(max(-diff, 0))
            avg_gain = sum(gains[:period]) / period
            avg_loss = sum(losses[:period]) / period
            rsi_vals = []
            for i in range(period, len(gains)):
                avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i]) / period
                rs  = avg_gain / avg_loss if avg_loss != 0 else 100
                rsi_vals.append(100 - (100 / (1 + rs)))
            dates = [str(d.date()) for d in hist.index[period:]]
            return {d: {"RSI": str(round(r, 2))} for d, r in zip(dates, rsi_vals)}
        except Exception as e:
            logger.error("get_rsi failed for %s: %s", self.symbol, e)
            return {}

    def get_sma(self, period: int = 50) -> dict:
        try:
            hist   = self._t.history(period="1y")
            closes = hist["Close"].tolist()
            dates  = [str(d.date()) for d in hist.index]
            if len(closes) < period:
                return {}
            result = {}
            for i in range(period - 1, len(closes)):
                sma = sum(closes[i - period + 1:i + 1]) / period
                result[dates[i]] = {"SMA": str(round(sma, 2))}
            return result
        except Exception as e:
            logger.error("get_sma failed for %s: %s", self.symbol, e)
            return {}

    def fetch_all(self) -> dict:
        """Single Ticker object, all data — yfinance caches internally."""
        return {
            "quote":    self.get_quote(),
            "daily":    self.get_daily(),
            "overview": self.get_overview(),
            "rsi":      self.get_rsi(),
            "sma50":    self.get_sma(50),
        }
