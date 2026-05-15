# Backend Pipeline Stages

**Orchestrator:** `backend/app/services/orchestration/pipeline.py`

| Stage | Service | Persist |
|-------|---------|---------|
| collect | `NewsCollectorService` | `raw_articles` |
| clean | `NewsCleanerService` | — |
| sentiment | `SentimentService` (FinBERT) | — |
| events | `EventExtractionService` | — |
| market | `MarketDataService` (Polygon) | `ohlcv_bars` |
| impact | `EventImpactScoringService` | `processed_articles` |
| compress | `NarrativeCompressionService` | — |
| vectors | `QdrantStoreService` | Qdrant |
| report | `ClaudeReportService` | `research_reports` |
| done | attach `_pipeline_meta`, Redis cache | — |

## Routes

| Path | File |
|------|------|
| `GET /api/v1/research/{ticker}` | `api/v1/routes/research.py` |
| `GET /api/v1/analogs/{ticker}/{event_type}` | `api/v1/routes/analogs.py` |
| `GET /api/v1/history/{ticker}` | `api/v1/routes/history.py` |
| `WS /api/v1/ws/research-progress` | `api/v1/routes/websocket.py` |

Rate limit: research default `10/minute` (`RATE_LIMIT_RESEARCH`).

## External limits

| Source | Cap |
|--------|-----|
| Finnhub | 60 articles |
| NewsAPI | pageSize 30 |
| Polygon news | 25 |
| Polygon OHLCV | 120 bars |
| Claude clusters | 15 |
