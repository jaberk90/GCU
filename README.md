# Stock Analysis Web Application
**GCU MSSE / MSSD Capstone Project**
Author: Jaber Kaal

---

## Project Overview

A three-tier web application that allows users to enter a stock ticker symbol
and receive a comprehensive analysis including:
- Real-time price summary
- Technical indicators (RSI, MACD, SMA-50, SMA-200)
- Fundamental metrics (P/E, EPS, ROE, profit margin, beta, dividend yield)
- ARIMA + LSTM price forecast with confidence score
- Buy / Hold / Sell recommendation

---

## Architecture

```
┌──────────────────┐     HTTP/JSON     ┌──────────────────────┐
│  Angular SPA     │ ────────────────► │  Flask REST API      │
│  (frontend/)     │                   │  (backend/)          │
│                  │ ◄──────────────── │                      │
│  Home Page       │                   │  /api/v1/validate    │
│  Dashboard       │                   │  /api/v1/analyze     │
│  Prediction Tab  │                   │  /api/v1/predict     │
└──────────────────┘                   └──────────┬───────────┘
                                                   │
                                        ┌──────────▼───────────┐
                                        │  External APIs       │
                                        │  Alpha Vantage       │
                                        │  (FMP optional)      │
                                        └──────────────────────┘
```

---

## Repository Structure

```
stock-analysis-app/
├── backend/
│   ├── app.py                   # Flask app factory
│   ├── requirements.txt
│   ├── .env.example             # Copy to .env with real keys
│   ├── routes/
│   │   ├── validate.py          # FR-2, FR-3
│   │   ├── analysis.py          # FR-1, FR-4, FR-5
│   │   └── predict.py           # FR-6
│   ├── services/
│   │   └── market_data.py       # FR-7 (caching)
│   └── analytics/
│       ├── technical.py         # FR-5, US-3
│       ├── fundamental.py       # FR-4, US-4
│       └── forecast.py          # FR-6, US-6 (ARIMA + LSTM)
├── frontend/
│   ├── package.json
│   └── src/app/
│       ├── home/                # US-1, FR-1
│       ├── dashboard/           # US-2,3,4,6 / FR-10
│       └── services/
│           └── stock.service.ts # All API calls
├── tests/
│   └── test_suite.py            # TC-01 through TC-10
└── docs/
    └── README.md
```

---

## Setup & Run

### Backend

```bash
cd backend

# 1. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and set ALPHAVANTAGE_API_KEY

# 4. Run development server
python app.py
# Server starts at http://localhost:5000
```

### Frontend

```bash
cd frontend

# 1. Install dependencies
npm install

# 2. Start development server
npm start
# App available at http://localhost:4200
```

### Run Tests

```bash
cd backend
pytest ../tests/test_suite.py -v
```

---

## API Endpoints

| Method | Endpoint              | Description                    | FR  |
|--------|-----------------------|--------------------------------|-----|
| POST   | /api/v1/validate      | Validate ticker format         | FR-2, FR-3 |
| POST   | /api/v1/analyze       | Full technical + fundamental   | FR-1, FR-4, FR-5 |
| POST   | /api/v1/predict       | ARIMA + LSTM forecast          | FR-6 |

### Example: POST /api/v1/analyze
```json
// Request
{ "symbol": "AAPL" }

// Response
{
  "symbol": "AAPL",
  "summary": { "price": 175.50, "change": 2.30, ... },
  "technical": [ { "name": "RSI (14)", "value": 55.23, "signal": "hold", ... }, ... ],
  "fundamental": { "valuation": { "pe_ratio": 28.5, "eps": 6.15, ... }, ... },
  "recommendation": { "action": "BUY", "reason": "4 of 5 indicators signal bullish conditions.", ... }
}
```

---

## Functional Requirements Traceability

| FR  | Requirement                             | Backend Module            | Test     |
|-----|-----------------------------------------|---------------------------|----------|
| FR-1  | Input valid stock symbol               | routes/validate.py        | TC-01    |
| FR-2  | Validate input; show error             | routes/validate.py        | TC-02    |
| FR-3  | Return error for invalid symbol        | routes/analysis.py        | TC-03    |
| FR-4  | Display fundamental metrics            | analytics/fundamental.py  | TC-04    |
| FR-5  | Technical indicators + moving averages | analytics/technical.py    | TC-05    |
| FR-6  | Forecast view + confidence score       | analytics/forecast.py     | TC-06    |
| FR-7  | Cache historical data                  | services/market_data.py   | TC-07    |
| FR-8  | Operational logs                       | app.py (logging)          | TC-08    |
| FR-9  | Guest access without login             | All routes (no auth)      | TC-09    |
| FR-10 | User-friendly tabbed layout            | dashboard component       | TC-10    |

---

## Non-Functional Requirements

- **Performance:** API responses target < 3 seconds (Alpha Vantage latency dependent)
- **Concurrency:** Stateless Flask design handles concurrent users
- **Security:** API keys stored server-side only via `.env`; never in frontend code
- **Usability:** Clear error messages for all invalid inputs; retry allowed
- **Reliability:** All modules fail safely; forecast returns error object, not crash

---

## References

1. Alpha Vantage API — https://www.alphavantage.co/documentation/
2. Flask — https://flask.palletsprojects.com/
3. Angular — https://angular.io/docs
4. TensorFlow / Keras — https://www.tensorflow.org/
5. statsmodels (ARIMA) — https://www.statsmodels.org/
6. Chart.js — https://www.chartjs.org/docs/
7. Sommerville, I. (2015). *Software Engineering* (10th ed.). Pearson.
