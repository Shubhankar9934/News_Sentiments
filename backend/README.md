# Financial News Research — Backend

Modular FastAPI service: collectors, FinBERT, Qdrant, Claude synthesis, PostgreSQL persistence.

## Quick start

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: `http://localhost:8000/docs` (Swagger) and `http://localhost:8000/redoc` (ReDoc).

Legacy monolith reference: `../news_pipeline_v3.py` (logic ported into `app/services`).

---

## IBKR Live Market Data (optional)

The dashboard supports an optional live IBKR feed alongside the frozen
"Re-Run Analysis" snapshot. Live prices and live Reverse-BWB option
opportunities flow into two new tables (`ticker_market_data`,
`ticker_live_option_opportunities`) and are exposed via three new
read-only endpoints:

- `GET /api/v1/tickers/{ticker}/market-data`
- `GET /api/v1/tickers/{ticker}/options-opportunities`
- `GET /api/v1/dashboard/live` (bulk; polled by the React grid every ~4s)

The analysis-snapshot path is **completely unchanged** — Decision,
Credit Safety, Risk, Confidence, summaries, etc. are still produced
exclusively by the watchlist batch and only refreshed when the user
clicks Re-Run Analysis.

### Prerequisites

1. **IB Gateway or TWS** running locally (or on a reachable host):
   - Default ports: `4001` (paper) / `4002` (live) for IB Gateway,
     `7497` / `7496` for TWS.
   - In Gateway → *Configure → Settings → API → Settings*, enable
     "ActiveX and Socket Clients" and set the trusted IP.
2. **Market-data subscriptions** — every watchlist symbol needs the
   relevant IBKR market-data subscription (US Equity Bundle for the
   underlyings, OPRA for the options chain). Without these IBKR returns
   error code `-10167` and the worker logs degrade to disconnected.
3. **`ib-async`** is added to `pyproject.toml` and is installed by
   `pip install -e ".[dev]"`.

### Configuration

Add the following to `.env` (all default to safe values that keep the
feature OFF):

```env
# Master switch. False = the dashboard runs exactly as before.
IBKR_ENABLED=false

IBKR_HOST=127.0.0.1
IBKR_PORT=4001          # 4001=paper, 4002=live, 7497/7496 for TWS
IBKR_CLIENT_ID=17
IBKR_PAPER=true
IBKR_CONNECT_TIMEOUT_S=10

MARKET_DATA_PRICE_FLUSH_MS=1000     # how often the price loop UPSERTs
MARKET_DATA_OPP_INTERVAL_S=45       # opportunity refresh cadence
MARKET_DATA_STALE_THRESHOLD_S=10    # quote freshness window

OPP_TARGET_DTE_MIN=7
OPP_TARGET_DTE_MAX=21
OPP_RANK_TOP_N_PER_SIDE=2
```

### Deployment constraints

- **Single uvicorn worker only** — IBKR Gateway permits exactly one
  client per `IBKR_CLIENT_ID`, so production must run with
  `uvicorn app.main:app --workers 1`. Multi-worker deployments would
  cause client-id collisions on Gateway. If horizontal scaling is
  needed later, split the `MarketDataWorker` into a sidecar process
  that exposes its data via internal HTTP/gRPC.
- The live worker only starts when `IBKR_ENABLED=true`. Flip the flag
  to `true` once Gateway connectivity is verified — the rest of the
  application is identical with the flag on or off.
- When IBKR disconnects mid-session, the worker:
  - stops UPSERTing rows,
  - marks the existing rows as `feed_status='disconnected'`, and
  - the API returns `feed_status='disconnected'` so the frontend
    surfaces a "Live data unavailable" banner. Existing analysis
    snapshots continue to render normally.

### Migration

The two new tables ship in `alembic` revision `0013_market_data_tables`.
Apply with:

```bash
alembic upgrade head
```

### Strict separation guarantee

The live worker (`app.services.market_data.*`) writes only to
`ticker_market_data` and `ticker_live_option_opportunities`. The
analysis batch (`app.services.dashboard.watchlist_batch`) writes only
to `ticker_reports`, `ticker_reverse_bwb_summary`, and
`ticker_option_opportunities`. There is no shared write path; the
boundary is verified by `tests/market_data/test_separation_static.py`.
