# Reverse BWB Trading Workstation — Deployment Checklist

The Workstation introduces a live IBKR market-data path (System B) that runs
alongside the existing analysis snapshot pipeline (System A). The two systems
are strictly separated: live ticks never overwrite snapshot fields, and the
re-run-analysis flow never touches `ticker_live_option_opportunities` or
`ticker_option_opportunity_history`.

## 1. Database migrations

Two new migrations land in `backend/alembic/versions/`:

- `0014_opportunity_history.py` — creates the append-only
  `ticker_option_opportunity_history` table.
- `0015_live_opportunities_extended.py` — extends
  `ticker_live_option_opportunities` with the Workstation columns
  (strikes, expiry_days, delta_pct, per-leg OI/Vol/IV/Mid,
  credit_efficiency, ranking_score, init_margin_source,
  underlying_price, iv, opportunity_version) and drops the now-obsolete
  `UNIQUE(ticker, side, rank)` constraint.

```bash
# Inside the backend container / venv:
alembic upgrade head
```

Verify both tables exist with the new columns:

```sql
\d ticker_live_option_opportunities
\d ticker_option_opportunity_history
SELECT indexname FROM pg_indexes
 WHERE tablename IN ('ticker_live_option_opportunities',
                     'ticker_option_opportunity_history');
```

## 2. Environment configuration

New variables (defaults shown — adjust for your IBKR pacing limits):

```bash
# Reverse BWB Workstation
OPP_DTE_MIN=0
OPP_DTE_MAX=14
OPP_WING_MIN_STRIKES=1
OPP_WING_MAX_STRIKES=20
OPP_MIN_LEG_OI=10
OPP_WHATIF_TOP_N=25            # WhatIf-refined rows per side per ticker
OPP_WHATIF_MAX_PER_MIN=12      # IBKR pacing budget for WhatIf orders
OPP_RECALC_PRICE_PCT=0.25      # underlying move that triggers recalc
OPP_RECALC_IV_PCT=3.0          # atm IV move that triggers recalc
OPP_RECALC_MAX_AGE_S=900       # forced recalc after this many seconds
WS_TICK_BATCH_MS=250           # tick debounce window for WebSocket fanout
```

Existing IBKR settings (`IBKR_ENABLED=true`, `IBKR_HOST`, `IBKR_PORT=4001`,
`IBKR_CLIENT_ID`) are unchanged. `OPP_RANK_TOP_N_PER_SIDE` is deprecated;
keep it for now but remove once external callers stop relying on it.

## 3. Backend deploy

Run a **single** worker (the IBKR gateway only allows one connection per
client id and the opportunity loop assumes a singleton scheduler):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

After boot, the structured logs should show:

```
market_data.worker.started watchlist=[SPY, QQQ, ...] price_flush_ms=1000 opp_interval_s=45
market_data.price_loop.started flush_seconds=1.0
market_data.opp_loop.started interval_s=45
```

## 4. Frontend deploy

Set the WebSocket base URL **once** at build time:

```bash
# .env.production
VITE_WS_BASE_URL=wss://api.example.com/api/v1
```

Then build & deploy as usual (Vite + static hosting):

```bash
pnpm --filter ./frontend build
```

## 5. Smoke checklist

After deploy:

1. **Live prices stream**
   - Open the dashboard. Within ~5 s, all 12 ticker cards should display
     prices changing on every tick.
   - Browser DevTools -> Network -> WS shows a single open WebSocket to
     `/api/v1/ws/market-data` with `tick` messages.

2. **Opportunities populate**
   - Within ~45 s of boot, each card's CALL and PUT panels should show
     **>>4 rows** for the index ETFs (SPY/QQQ). The header counter shows
     the row count.
   - Click any column header — the table sorts in place.

3. **Analysis snapshot stays frozen**
   - Click "Re-Run Analysis" on a card. The Decision / Credit Safety /
     Risk / Confidence / Outlook / Expected Range / Pin Risk / Event Risk
     / Summary fields update.
   - During the next minute (with the live tick stream still active),
     those fields **do not change**. Only the live header price and the
     opportunity tables tick.

4. **Full Report opportunity explorer**
   - Open the Full Report for a watchlist ticker. Section 3 ("Reverse BWB
     Opportunity Explorer") should support every filter / sort knob and
     render the full row set via virtualization.
   - The history date picker reads from `ticker_option_opportunity_history`.

5. **Health endpoint**
   - `GET /api/v1/market-data/health` returns
     `{ ibkr_state: "connected", last_quote_ts: ..., last_opp_version_per_ticker: {...}, whatif_budget_remaining: N }`.

6. **Prometheus counters**
   - Scrape `/metrics` and confirm increasing values for
     `opps_generated_total`, `opps_persisted_total`,
     `opps_history_appended_total`, `opportunity_version_total`,
     `ws_messages_total{type="tick"}`,
     `ws_messages_total{type="opportunity_version"}`.

## 6. Rollback

The migrations are reversible:

```bash
alembic downgrade -1   # backs out 0015 (drops new columns + restores constraint)
alembic downgrade -1   # backs out 0014 (drops history table)
```

The old `OPP_RANK_TOP_N_PER_SIDE` code path still works for legacy
clients — only the column set grew.
