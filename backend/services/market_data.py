"""
MarketDataService — FR-7
Uses yfinance — no API key, no rate limits, full fundamentals + technicals.
"""

import logging
import yfinance as yf

logger = logging.getLogger(__name__)


class MarketDataService:

    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        self._ticker = yf.Ticker(self.symbol)

    def get_quote(self) -> dict:
        """Current price, change, volume."""
        try:
            info = self._ticker.fast_info
            hist = self._ticker.history(period="2d")
            if hist.empty:
                return {}

            current   = float(hist["Close"].iloc[-1])
            prev      = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
            change    = round(current - prev, 2)
            change_pct = round((change / prev) * 100, 2) if prev else 0

            return {
                "05. price":           str(round(current, 2)),
                "09. change":          str(change),
                "10. change percent":  f"{change_pct}%",
                "02. open":            str(round(float(hist["Open"].iloc[-1]), 2)),
                "03. high":            str(round(float(hist["High"].iloc[-1]), 2)),
                "04. low":             str(round(float(hist["Low"].iloc[-1]), 2)),
                "08. previous close":  str(round(prev, 2)),
                "06. volume":          str(int(hist["Volume"].iloc[-1])),
            }
        except Exception as e:
            logger.error("get_quote failed for %s: %s", self.symbol, e)
            return {}

    def get_daily(self) -> dict:
        """6 months of daily OHLCV — plenty for ARIMA + LSTM."""
        try:
            hist = self._ticker.history(period="6mo")
            if hist.empty:
                return {}
            result = {}
            for date, row in hist.iterrows():
                key = str(date.date())
                result[key] = {
                    "1. open":   str(round(float(row["Open"]),   2)),
                    "2. high":   str(round(float(row["High"]),   2)),
                    "3. low":    str(round(float(row["Low"]),    2)),
                    "4. close":  str(round(float(row["Close"]),  2)),
                    "5. volume": str(int(row["Volume"])),
                }
            return result
        except Exception as e:
            logger.error("get_daily failed for %s: %s", self.symbol, e)
            return {}

    def get_overview(self) -> dict:
        """Full fundamental data — far more complete than Alpha Vantage free."""
        try:
            info = self._ticker.info
            if not info or not info.get("symbol"):
                return {}

            def pct(v):
                return f"{round(v * 100, 2)}%" if v else "—"

            def fmt(v, dec=2):
                return str(round(float(v), dec)) if v else "—"

            return {
                "Symbol":                  info.get("symbol", self.symbol),
                "Name":                    info.get("longName", "—"),
                "Exchange":                info.get("exchange", "—"),
                "Sector":                  info.get("sector", "—"),
                "Industry":                info.get("industry", "—"),
                "Description":             info.get("longBusinessSummary", "—"),
                "MarketCapitalization":    str(info.get("marketCap", "")),
                "PERatio":                 fmt(info.get("trailingPE")),
                "ForwardPE":               fmt(info.get("forwardPE")),
                "EPS":                     fmt(info.get("trailingEps")),
                "EVToEBITDA":              fmt(info.get("enterpriseToEbitda")),
                "PriceToBookRatio":        fmt(info.get("priceToBook")),
                "PriceToSalesRatioTTM":    fmt(info.get("priceToSalesTrailing12Months")),
                "ReturnOnEquityTTM":       fmt(info.get("returnOnEquity")),
                "ReturnOnAssetsTTM":       fmt(info.get("returnOnAssets")),
                "ProfitMargin":            fmt(info.get("profitMargins")),
                "OperatingMarginTTM":      fmt(info.get("operatingMargins")),
                "RevenueTTM":              str(info.get("totalRevenue", "")),
                "GrossProfitTTM":          str(info.get("grossProfits", "")),
                "Beta":                    fmt(info.get("beta")),
                "DividendYield":           fmt(info.get("dividendYield")),
                "BookValue":               fmt(info.get("bookValue")),
                "SharesOutstanding":       str(info.get("sharesOutstanding", "")),
                "52WeekHigh":              fmt(info.get("fiftyTwoWeekHigh")),
                "52WeekLow":               fmt(info.get("fiftyTwoWeekLow")),
            }
        except Exception as e:
            logger.error("get_overview failed for %s: %s", self.symbol, e)
            return {}

    def get_rsi(self, period: int = 14) -> dict:
        """RSI calculated from daily close prices."""
        try:
            hist   = self._ticker.history(period="3mo")
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
                rsi = 100 - (100 / (1 + rs))
                rsi_vals.append(rsi)

            dates = [str(d.date()) for d in hist.index[period:]]
            return {d: {"RSI": str(round(r, 2))}
                    for d, r in zip(dates, rsi_vals)}
        except Exception as e:
            logger.error("get_rsi failed for %s: %s", self.symbol, e)
            return {}

    def get_sma(self, period: int = 50) -> dict:
        """SMA calculated from daily close prices."""
        try:
            hist   = self._ticker.history(period="1y")
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
        """Fetch all data — yfinance is fast, no rate limits."""
        return {
            "quote":    self.get_quote(),
            "daily":    self.get_daily(),
            "overview": self.get_overview(),
            "rsi":      self.get_rsi(),
            "sma50":    self.get_sma(50),
        }
