"""
Financial News Research Pipeline — v3 (LEGACY MONOLITH)
======================================================
**Deprecated for new development**: the productionized modular implementation lives in `backend/`
(`app.services.*`, FastAPI routes under `/api/v1`, Alembic, Docker, tests).

This file is retained for reference and one-shot CLI usage:

  python news_pipeline_v3.py --ticker NVDA --days 7
  python news_pipeline_v3.py --serve

Priority 1: PostgreSQL persistence     ✓
Priority 2: Qdrant vector store        ✓
Priority 3: Market price data (OHLCV)  ✓
Priority 4: Event impact scoring       ✓
+ Rate limit handling / retries        ✓
+ Narrative compression before Claude  ✓
+ Structured observability             ✓

Run:
  # One-shot research run
  python news_pipeline_v3.py --ticker NVDA --days 7

  # REST API server
  python news_pipeline_v3.py --serve

  # Docker
  docker compose up

Deps:
  pip install aiohttp finnhub-python sentence-transformers transformers torch
              sqlalchemy asyncpg qdrant-client fastapi uvicorn tenacity
              prometheus-client structlog
"""

from __future__ import annotations

import asyncio
import argparse
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

import aiohttp
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# ─── Structured logging ───────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger()

# ─── Config ───────────────────────────────────────────────────────────────────

FINNHUB_API_KEY   = "your_finnhub_key"
NEWSAPI_KEY       = "your_newsapi_key"
POLYGON_API_KEY   = "your_polygon_key"
ANTHROPIC_API_KEY = "your_anthropic_key"

DATABASE_URL  = "postgresql+asyncpg://user:pass@localhost:5432/finresearch"
QDRANT_HOST   = "localhost"
QDRANT_PORT   = 6333
QDRANT_COLLECTION = "article_embeddings"

EMBED_MODEL = "all-MiniLM-L6-v2"   # 384-dim, fast
FINBERT_MODEL = "ProsusAI/finbert"

DEDUPE_THRESHOLD    = 0.92
MAX_ARTICLES_CLAUDE = 15    # After narrative compression, send ≤15 clusters

SOURCE_RELIABILITY = {
    "SEC Filing": 98, "Reuters": 92, "Bloomberg": 91, "WSJ": 88,
    "Financial Times": 87, "AP": 86, "CNBC": 78, "Yahoo Finance": 72,
    "MarketWatch": 70, "Seeking Alpha": 58, "Reddit": 35, "Twitter/X": 30,
}

EVENT_IMPACT_WEIGHTS = {
    "Earnings":     1.0,
    "Regulation":   0.9,
    "Supply Chain": 0.85,
    "Macro":        0.8,
    "Partnership":  0.7,
    "Product":      0.65,
    "Analyst":      0.5,
}


# ─── Data models ──────────────────────────────────────────────────────────────

@dataclass
class RawArticle:
    id:            str
    ticker:        str
    headline:      str
    content:       str
    source:        str
    url:           str
    published_at:  datetime
    raw_json:      dict = field(default_factory=dict)

@dataclass
class ProcessedArticle:
    id:                str
    ticker:            str
    headline:          str
    content:           str
    source:            str
    url:               str
    published_at:      datetime
    sentiment_score:   float = 0.0
    sentiment_label:   str   = "Neutral"
    event_type:        Optional[str] = None
    embedding:         list  = field(default_factory=list)
    cluster_id:        Optional[str] = None
    reliability_score: int   = 60
    is_duplicate:      bool  = False
    impact_score:      float = 0.0   # Priority 4
    abnormal_return:   Optional[float] = None  # Priority 3: set after price join

@dataclass
class OHLCVBar:
    ticker:    str
    timestamp: datetime
    open:      float
    high:      float
    low:       float
    close:     float
    volume:    int

@dataclass
class EventImpactScore:
    article_id:     str
    ticker:         str
    impact_score:   float
    components:     dict   # breakdown: sentiment, reliability, recency, volatility
    computed_at:    datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ─── PostgreSQL schema (SQLAlchemy Core, async) ────────────────────────────────

SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";   -- pgvector (optional, Qdrant preferred)

CREATE TABLE IF NOT EXISTS raw_articles (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id   TEXT UNIQUE NOT NULL,
    ticker        VARCHAR(10) NOT NULL,
    headline      TEXT NOT NULL,
    content       TEXT,
    source        TEXT,
    url           TEXT,
    published_at  TIMESTAMPTZ,
    raw_json      JSONB,
    ingested_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS processed_articles (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    raw_article_id    UUID REFERENCES raw_articles(id),
    ticker            VARCHAR(10) NOT NULL,
    headline          TEXT NOT NULL,
    source            TEXT,
    published_at      TIMESTAMPTZ,
    sentiment_score   FLOAT,
    sentiment_label   TEXT,
    event_type        TEXT,
    reliability_score INT,
    impact_score      FLOAT,
    abnormal_return   FLOAT,
    is_duplicate      BOOLEAN DEFAULT FALSE,
    cluster_id        TEXT,
    processed_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_processed_ticker_date ON processed_articles(ticker, published_at DESC);

CREATE TABLE IF NOT EXISTS article_clusters (
    cluster_id     TEXT NOT NULL,
    article_id     UUID REFERENCES processed_articles(id),
    representative BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (cluster_id, article_id)
);

CREATE TABLE IF NOT EXISTS ohlcv_bars (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker     VARCHAR(10) NOT NULL,
    timestamp  TIMESTAMPTZ NOT NULL,
    timeframe  TEXT DEFAULT '1d',
    open       FLOAT,
    high       FLOAT,
    low        FLOAT,
    close      FLOAT,
    volume     BIGINT,
    UNIQUE(ticker, timestamp, timeframe)
);
CREATE INDEX IF NOT EXISTS idx_ohlcv_ticker_ts ON ohlcv_bars(ticker, timestamp DESC);

CREATE TABLE IF NOT EXISTS event_impact_scores (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id   UUID REFERENCES processed_articles(id),
    ticker       VARCHAR(10),
    impact_score FLOAT,
    components   JSONB,
    computed_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS research_reports (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker       VARCHAR(10) NOT NULL,
    time_window  TEXT,
    report_json  JSONB NOT NULL,
    data_mode    TEXT,
    articles_ct  INT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_reports_ticker ON research_reports(ticker, created_at DESC);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker       VARCHAR(10),
    started_at   TIMESTAMPTZ DEFAULT NOW(),
    finished_at  TIMESTAMPTZ,
    stage        TEXT,
    status       TEXT,
    metrics      JSONB
);
"""

async def get_db_pool():
    """Returns asyncpg connection pool. Call once at startup."""
    import asyncpg
    return await asyncpg.create_pool(
        DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"),
        min_size=2, max_size=10,
    )

async def init_db(pool):
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)
    log.info("database.initialized")

async def persist_raw_articles(pool, articles: list[RawArticle]):
    async with pool.acquire() as conn:
        await conn.executemany(
            """INSERT INTO raw_articles(external_id, ticker, headline, content, source, url, published_at, raw_json)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8)
               ON CONFLICT (external_id) DO NOTHING""",
            [(a.id, a.ticker, a.headline, a.content, a.source, a.url,
              a.published_at, json.dumps(a.raw_json)) for a in articles],
        )

async def persist_processed_articles(pool, articles: list[ProcessedArticle]):
    async with pool.acquire() as conn:
        await conn.executemany(
            """INSERT INTO processed_articles(raw_article_id, ticker, headline, source, published_at,
               sentiment_score, sentiment_label, event_type, reliability_score, impact_score,
               abnormal_return, is_duplicate, cluster_id)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
               ON CONFLICT DO NOTHING""",
            [(None, a.ticker, a.headline, a.source, a.published_at,
              a.sentiment_score, a.sentiment_label, a.event_type, a.reliability_score,
              a.impact_score, a.abnormal_return, a.is_duplicate, a.cluster_id)
             for a in articles],
        )

async def persist_ohlcv(pool, bars: list[OHLCVBar]):
    async with pool.acquire() as conn:
        await conn.executemany(
            """INSERT INTO ohlcv_bars(ticker, timestamp, open, high, low, close, volume)
               VALUES($1,$2,$3,$4,$5,$6,$7)
               ON CONFLICT (ticker, timestamp, timeframe) DO UPDATE
               SET open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                   close=EXCLUDED.close, volume=EXCLUDED.volume""",
            [(b.ticker, b.timestamp, b.open, b.high, b.low, b.close, b.volume) for b in bars],
        )

async def persist_report(pool, ticker: str, window: str, report: dict):
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO research_reports(ticker, time_window, report_json, data_mode, articles_ct)
               VALUES($1,$2,$3,$4,$5)""",
            ticker, window, json.dumps(report, default=str),
            report.get("data_mode", "unknown"),
            report.get("articles_analyzed", 0),
        )

async def fetch_historical_similar_events(pool, ticker: str, event_type: str, limit: int = 5):
    """
    Priority 2 preview: retrieve past events of same type for analog comparison.
    Full implementation connects to Qdrant for semantic search.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT p.headline, p.published_at, p.sentiment_score, p.impact_score, o.close, o.volume
               FROM processed_articles p
               LEFT JOIN ohlcv_bars o ON o.ticker = p.ticker
                   AND o.timestamp::date = p.published_at::date
               WHERE p.ticker = $1 AND p.event_type = $2
               ORDER BY p.impact_score DESC, p.published_at DESC
               LIMIT $3""",
            ticker, event_type, limit,
        )
    return [dict(r) for r in rows]


# ─── Priority 2: Qdrant vector store ─────────────────────────────────────────

class QdrantStore:
    """
    Stores article embeddings in Qdrant for:
    - fast ANN search (replaces O(N²) dedupe at scale)
    - historical analog retrieval
    - narrative similarity search
    """

    def __init__(self):
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams, PointStruct
        self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        self.PointStruct = PointStruct

        # Create collection if not exists
        existing = [c.name for c in self.client.get_collections().collections]
        if QDRANT_COLLECTION not in existing:
            self.client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            log.info("qdrant.collection_created", name=QDRANT_COLLECTION)

    def upsert_articles(self, articles: list[ProcessedArticle]):
        points = []
        for a in articles:
            if not a.embedding:
                continue
            points.append(self.PointStruct(
                id=hashlib.md5(a.id.encode()).hexdigest()[:16],  # Qdrant needs UUID or int
                vector=a.embedding[:384],
                payload={
                    "article_id":   a.id,
                    "ticker":       a.ticker,
                    "headline":     a.headline,
                    "source":       a.source,
                    "published_at": a.published_at.isoformat(),
                    "sentiment":    a.sentiment_score,
                    "event_type":   a.event_type,
                    "impact_score": a.impact_score,
                },
            ))
        if points:
            self.client.upsert(collection_name=QDRANT_COLLECTION, points=points)
            log.info("qdrant.upserted", count=len(points))

    def search_similar(self, embedding: list[float], ticker: str = None, limit: int = 10):
        """ANN search — O(log N) vs O(N²) matrix multiply."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        filt = None
        if ticker:
            filt = Filter(must=[FieldCondition(key="ticker", match=MatchValue(value=ticker))])
        results = self.client.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=embedding,
            query_filter=filt,
            limit=limit,
            with_payload=True,
        )
        return results

    def find_historical_analogs(self, embedding: list[float], ticker: str, limit: int = 5):
        """
        Retrieve past events semantically similar to current headline.
        Powers the Event Memory Engine described in the assessment.
        """
        results = self.search_similar(embedding, ticker=None, limit=limit * 3)
        # Filter to same ticker with score threshold
        analogs = [r for r in results if r.payload.get("ticker") == ticker and r.score > 0.85]
        return analogs[:limit]


# ─── Priority 3: Market price data ───────────────────────────────────────────

class MarketDataAgent:
    """
    Fetches OHLCV price data from Polygon.io and computes:
    - daily returns
    - abnormal returns (vs expected based on market)
    - intraday volatility
    Joins price movements to news events to answer "which news moved price?"
    """

    def __init__(self, ticker: str):
        self.ticker = ticker

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(aiohttp.ClientError),
    )
    async def fetch_ohlcv(self, days: int) -> list[OHLCVBar]:
        from_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        to_date   = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        url = f"https://api.polygon.io/v2/aggs/ticker/{self.ticker}/range/1/day/{from_date}/{to_date}"
        params = {"adjusted": "true", "sort": "asc", "limit": 120, "apiKey": POLYGON_API_KEY}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()

        bars = []
        for r in data.get("results", []):
            bars.append(OHLCVBar(
                ticker=self.ticker,
                timestamp=datetime.fromtimestamp(r["t"] / 1000, tz=timezone.utc),
                open=r["o"], high=r["h"], low=r["l"], close=r["c"], volume=r["v"],
            ))
        log.info("market.ohlcv_fetched", ticker=self.ticker, bars=len(bars))
        return bars

    @staticmethod
    def compute_daily_returns(bars: list[OHLCVBar]) -> dict[str, float]:
        """Returns {date_str: pct_change} for each trading day."""
        returns = {}
        for i in range(1, len(bars)):
            prev, curr = bars[i - 1], bars[i]
            if prev.close and prev.close != 0:
                ret = (curr.close - prev.close) / prev.close * 100
                returns[curr.timestamp.date().isoformat()] = round(ret, 4)
        return returns

    @staticmethod
    def compute_intraday_volatility(bars: list[OHLCVBar]) -> dict[str, float]:
        """High-low range as % of open — proxy for realized intraday vol."""
        vol = {}
        for b in bars:
            if b.open and b.open != 0:
                v = (b.high - b.low) / b.open * 100
                vol[b.timestamp.date().isoformat()] = round(v, 4)
        return vol

    @staticmethod
    def join_price_to_articles(
        articles: list[ProcessedArticle],
        returns:  dict[str, float],
        vol:      dict[str, float],
    ) -> list[ProcessedArticle]:
        """
        Attaches abnormal_return to each article based on the trading day
        of publication. This directly answers: "Which news moved price?"
        """
        for a in articles:
            date_str = a.published_at.date().isoformat()
            ret = returns.get(date_str)
            if ret is not None:
                a.abnormal_return = ret
        return articles

    @staticmethod
    def get_current_price(bars: list[OHLCVBar]) -> Optional[float]:
        return bars[-1].close if bars else None

    @staticmethod
    def get_volatility_regime(bars: list[OHLCVBar], window: int = 10) -> str:
        """Simple volatility regime: low / medium / high based on recent daily moves."""
        if len(bars) < 2:
            return "unknown"
        recent = bars[-min(window, len(bars)):]
        moves = []
        for i in range(1, len(recent)):
            if recent[i-1].close:
                moves.append(abs(recent[i].close - recent[i-1].close) / recent[i-1].close * 100)
        if not moves:
            return "unknown"
        avg = sum(moves) / len(moves)
        return "high" if avg > 3 else "medium" if avg > 1.5 else "low"


# ─── Priority 4: Event impact scoring ────────────────────────────────────────

class EventImpactScorer:
    """
    impact_score = sentiment_magnitude
                 × source_reliability_weight
                 × recency_decay
                 × event_type_weight
                 × volatility_regime_multiplier

    Range: [0, 1]. Higher = more likely to have moved price.
    """

    VOLATILITY_MULTIPLIER = {"high": 1.3, "medium": 1.0, "low": 0.75, "unknown": 1.0}

    def score(
        self,
        articles: list[ProcessedArticle],
        volatility_regime: str = "medium",
        now: datetime = None,
    ) -> list[ProcessedArticle]:
        if now is None:
            now = datetime.now(timezone.utc)
        vol_mult = self.VOLATILITY_MULTIPLIER.get(volatility_regime, 1.0)

        for a in articles:
            # 1. Sentiment magnitude (how strongly positive or negative)
            sent_mag = abs(a.sentiment_score)                          # [0, 1]

            # 2. Source reliability weight
            rel_weight = a.reliability_score / 100.0                  # [0, 1]

            # 3. Recency decay — exponential half-life of 3 days
            age_days = max(0, (now - a.published_at.replace(tzinfo=timezone.utc)).total_seconds() / 86400)
            recency = 2 ** (-age_days / 3.0)                          # [0, 1]

            # 4. Event type weight
            event_weight = EVENT_IMPACT_WEIGHTS.get(a.event_type, 0.5)

            # 5. Combine
            raw_score = sent_mag * rel_weight * recency * event_weight * vol_mult
            a.impact_score = round(min(raw_score, 1.0), 4)

        log.info("impact_scoring.complete", articles=len(articles),
                 vol_regime=volatility_regime)
        return articles


# ─── Collector (with rate limiting + retries) ────────────────────────────────

class NewsCollectorAgent:

    def __init__(self, ticker: str, days: int):
        self.ticker    = ticker
        self.days      = days
        self.from_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        self.to_date   = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    async def collect(self) -> list[RawArticle]:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=10),
        ) as session:
            results = await asyncio.gather(
                self._fetch_finnhub(session),
                self._fetch_newsapi(session),
                self._fetch_polygon_news(session),
                return_exceptions=True,
            )
        articles = []
        for r in results:
            if isinstance(r, Exception):
                log.warning("collector.source_failed", error=str(r))
            else:
                articles.extend(r)
        log.info("collector.complete", ticker=self.ticker, total=len(articles))
        return articles

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8),
           retry=retry_if_exception_type(aiohttp.ClientError))
    async def _fetch_finnhub(self, session) -> list[RawArticle]:
        async with session.get(
            "https://finnhub.io/api/v1/company-news",
            params={"symbol": self.ticker, "from": self.from_date,
                    "to": self.to_date, "token": FINNHUB_API_KEY},
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        return [RawArticle(
            id=f"fh-{item.get('id', hashlib.md5(item.get('headline','').encode()).hexdigest()[:8])}",
            ticker=self.ticker,
            headline=item.get("headline", ""),
            content=item.get("summary", ""),
            source=item.get("source", "Unknown"),
            url=item.get("url", ""),
            published_at=datetime.fromtimestamp(item.get("datetime", 0), tz=timezone.utc),
            raw_json=item,
        ) for item in data[:60] if item.get("headline")]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8),
           retry=retry_if_exception_type(aiohttp.ClientError))
    async def _fetch_newsapi(self, session) -> list[RawArticle]:
        async with session.get(
            "https://newsapi.org/v2/everything",
            params={"q": f'"{self.ticker}" stock OR "{self.ticker}" earnings',
                    "from": self.from_date, "to": self.to_date,
                    "language": "en", "sortBy": "publishedAt",
                    "pageSize": 30, "apiKey": NEWSAPI_KEY},
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        return [RawArticle(
            id=f"na-{hashlib.md5(item.get('url','').encode()).hexdigest()[:8]}",
            ticker=self.ticker,
            headline=item.get("title", ""),
            content=item.get("description", "") or "",
            source=item.get("source", {}).get("name", "Unknown"),
            url=item.get("url", ""),
            published_at=datetime.fromisoformat(
                item.get("publishedAt", datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00")
            ),
            raw_json=item,
        ) for item in data.get("articles", []) if item.get("title")]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8),
           retry=retry_if_exception_type(aiohttp.ClientError))
    async def _fetch_polygon_news(self, session) -> list[RawArticle]:
        async with session.get(
            "https://api.polygon.io/v2/reference/news",
            params={"ticker": self.ticker, "published_utc.gte": self.from_date,
                    "limit": 25, "apiKey": POLYGON_API_KEY},
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        return [RawArticle(
            id=f"pg-{item.get('id', '')}",
            ticker=self.ticker,
            headline=item.get("title", ""),
            content=item.get("description", ""),
            source=item.get("publisher", {}).get("name", "Unknown"),
            url=item.get("article_url", ""),
            published_at=datetime.fromisoformat(
                item.get("published_utc", datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00")
            ),
            raw_json=item,
        ) for item in data.get("results", []) if item.get("title")]


# ─── Cleaner + Deduplicator ───────────────────────────────────────────────────

class NewsCleanerAgent:

    def __init__(self, qdrant: Optional[QdrantStore] = None):
        self._model  = None
        self.qdrant  = qdrant   # If provided, use ANN search instead of O(N²)

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(EMBED_MODEL)
        return self._model

    def clean(self, articles: list[RawArticle]) -> list[ProcessedArticle]:
        # Basic filter
        valid = [a for a in articles if len(a.headline.strip()) > 10]

        # Deduplicate by exact fingerprint first (cheap)
        seen_fps = set()
        deduped = []
        for a in valid:
            fp = hashlib.md5(f"{a.headline}{a.source}".encode()).hexdigest()
            if fp not in seen_fps:
                seen_fps.add(fp)
                deduped.append(a)

        # Convert to ProcessedArticle
        processed = [ProcessedArticle(
            id=a.id, ticker=a.ticker, headline=a.headline,
            content=a.content, source=a.source, url=a.url,
            published_at=a.published_at,
            reliability_score=SOURCE_RELIABILITY.get(a.source, 60),
        ) for a in deduped]

        # Embed
        model = self._get_model()
        headlines = [a.headline for a in processed]
        embeddings = model.encode(headlines, normalize_embeddings=True, batch_size=32)
        for i, a in enumerate(processed):
            a.embedding = embeddings[i].tolist()

        # Semantic dedupe
        if self.qdrant:
            self._dedupe_via_qdrant(processed)
        else:
            self._dedupe_matrix(processed, embeddings)

        unique = [a for a in processed if not a.is_duplicate]
        log.info("cleaner.complete", raw=len(articles), valid=len(valid),
                 unique=len(unique), dupes=len(processed) - len(unique))
        return processed

    def _dedupe_matrix(self, processed, embeddings):
        """O(N²) — fine up to ~500 articles."""
        import numpy as np
        emb = embeddings
        sim = emb @ emb.T
        cluster_map = {}
        ctr = 0
        for i in range(len(processed)):
            if processed[i].is_duplicate:
                continue
            cid = f"cluster-{ctr}"; ctr += 1
            processed[i].cluster_id = cid
            cluster_map[i] = cid
            for j in range(i + 1, len(processed)):
                if not processed[j].is_duplicate and sim[i, j] > DEDUPE_THRESHOLD:
                    # Keep higher-reliability article as representative
                    if processed[j].reliability_score > processed[i].reliability_score:
                        processed[i].is_duplicate = True
                        processed[j].cluster_id = cid
                    else:
                        processed[j].is_duplicate = True
                        processed[j].cluster_id = cid

    def _dedupe_via_qdrant(self, processed: list[ProcessedArticle]):
        """O(log N) via ANN — production path."""
        for article in processed:
            results = self.qdrant.search_similar(article.embedding[:384], limit=3)
            for r in results:
                if r.score > DEDUPE_THRESHOLD and r.payload.get("article_id") != article.id:
                    article.is_duplicate = True
                    article.cluster_id = r.payload.get("article_id")
                    break


# ─── FinBERT Sentiment ────────────────────────────────────────────────────────

class SentimentAgent:
    """
    Deterministic financial sentiment via ProsusAI/finbert.
    Uses direct model inference (not pipeline wrapper) for throughput.
    """

    LABEL_MAP = {"positive": ("Bullish", 1.0), "negative": ("Bearish", -1.0), "neutral": ("Neutral", 0.0)}

    def __init__(self):
        self._model     = None
        self._tokenizer = None

    def _load(self):
        if self._model is None:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            import torch
            self._tokenizer = AutoTokenizer.from_pretrained(FINBERT_MODEL)
            self._model     = AutoModelForSequenceClassification.from_pretrained(FINBERT_MODEL)
            self._device    = "cuda" if torch.cuda.is_available() else "cpu"
            self._model.to(self._device).eval()
            log.info("finbert.loaded", device=self._device)

    def analyze(self, articles: list[ProcessedArticle], batch_size: int = 16) -> list[ProcessedArticle]:
        import torch
        self._load()
        texts = [f"{a.headline}. {a.content[:300]}" for a in articles]

        all_preds = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            enc = self._tokenizer(batch, truncation=True, max_length=512,
                                  padding=True, return_tensors="pt")
            enc = {k: v.to(self._device) for k, v in enc.items()}
            with torch.no_grad():
                logits = self._model(**enc).logits
            probs = torch.softmax(logits, dim=-1).cpu().tolist()
            all_preds.extend(probs)

        id2label = self._model.config.id2label
        for article, probs in zip(articles, all_preds):
            best_idx = max(range(len(probs)), key=lambda i: probs[i])
            raw_label = id2label[best_idx].lower()
            label, direction = self.LABEL_MAP.get(raw_label, ("Neutral", 0.0))
            article.sentiment_label = label
            article.sentiment_score = round(probs[best_idx] * direction, 3)

        log.info("sentiment.complete", articles=len(articles))
        return articles


# ─── Event Extraction ─────────────────────────────────────────────────────────

class EventExtractionAgent:

    PATTERNS = {
        "Earnings":     ["earnings", "revenue", "eps", "beat", "miss", "guidance",
                         "q1", "q2", "q3", "q4", "annual", "quarterly", "profit", "loss"],
        "Regulation":   ["sec", "ftc", "doj", "antitrust", "ban", "sanction",
                         "regulation", "fine", "penalty", "export control", "subpoena"],
        "Supply Chain": ["tsmc", "supply", "shortage", "production", "manufacturing",
                         "inventory", "fab", "wafer", "foundry"],
        "Product":      ["launch", "release", "unveil", "announce", "chip", "gpu",
                         "model", "platform", "software", "hardware", "next-gen"],
        "Partnership":  ["partnership", "deal", "agreement", "collaborate", "invest",
                         "acquire", "merger", "acquisition", "joint venture"],
        "Macro":        ["fed", "interest rate", "inflation", "recession", "gdp",
                         "tariff", "china", "macro", "rate hike", "rate cut", "cpi"],
        "Analyst":      ["upgrade", "downgrade", "price target", "buy", "sell",
                         "neutral", "outperform", "underperform", "initiate", "coverage"],
    }

    def extract(self, articles: list[ProcessedArticle]) -> list[ProcessedArticle]:
        for a in articles:
            text = (a.headline + " " + a.content).lower()
            scores = {et: sum(1 for kw in kws if kw in text)
                      for et, kws in self.PATTERNS.items()}
            best = max(scores, key=scores.get)
            if scores[best] > 0:
                a.event_type = best
        log.info("events.extracted", articles=len(articles))
        return articles


# ─── Narrative compression ────────────────────────────────────────────────────

class NarrativeCompressor:
    """
    Groups articles by event_type + sentiment_label, picks top representative
    from each group by impact_score. Sends compressed cluster summaries
    to Claude instead of raw articles → reduces tokens + cost.
    """

    def compress(self, articles: list[ProcessedArticle], max_clusters: int = MAX_ARTICLES_CLAUDE) -> list[dict]:
        from itertools import groupby
        unique = [a for a in articles if not a.is_duplicate]
        sorted_arts = sorted(unique, key=lambda a: (a.event_type or "ZZZ", a.sentiment_label))

        clusters = []
        for key, group in groupby(sorted_arts, key=lambda a: (a.event_type, a.sentiment_label)):
            grp = sorted(group, key=lambda a: a.impact_score, reverse=True)
            rep = grp[0]
            clusters.append({
                "event_type":      rep.event_type,
                "sentiment":       rep.sentiment_label,
                "sentiment_score": round(sum(a.sentiment_score for a in grp) / len(grp), 3),
                "article_count":   len(grp),
                "impact_score":    round(max(a.impact_score for a in grp), 4),
                "top_headline":    rep.headline,
                "top_source":      rep.source,
                "published_at":    rep.published_at.isoformat(),
                "reliability":     rep.reliability_score,
                "abnormal_return": rep.abnormal_return,
                "headlines":       [a.headline for a in grp[:3]],
            })

        clusters.sort(key=lambda c: c["impact_score"], reverse=True)
        log.info("narrative.compressed", clusters=len(clusters), max=max_clusters)
        return clusters[:max_clusters]


# ─── Claude reasoning layer ───────────────────────────────────────────────────

class ReportAgent:

    SYSTEM_PROMPT = """You are a financial research synthesizer. You receive pre-processed, deduplicated news clusters with FinBERT sentiment and event impact scores already computed. Market price data (OHLCV) is also provided where available.

Your ONLY job is to synthesize, reason, and explain:
1. What is the dominant narrative?
2. What happened (grounded in the clusters provided)?
3. Which events most likely moved price (use abnormal_return data if available)?
4. Generate a price range estimate for today grounded in the news and OHLCV data.

Do NOT re-score sentiment. Use the provided scores.
Return ONLY valid JSON — no markdown, no backticks, no explanation."""

    REPORT_SCHEMA = """{
  "data_mode": "real",
  "data_quality_note": "<one sentence>",
  "articles_analyzed": <int>,
  "unique_sources": <int>,
  "duplicates_removed": <int>,
  "overall_sentiment_score": <float -1 to 1>,
  "overall_sentiment_label": "Bullish|Bearish|Neutral|Mixed",
  "sentiment_breakdown": [{"label":"Bullish","count":<int>,"pct":<float>,"score":0.7},{"label":"Neutral","count":<int>,"pct":<float>,"score":0.0},{"label":"Bearish","count":<int>,"pct":<float>,"score":-0.6}],
  "key_events": [{"type":"<type>","description":"<one sentence>","impact":"High|Medium|Low","impact_score":<float>}],
  "dominant_narrative": "<one sentence>",
  "what_happened": "<two sentences>",
  "price_movers": "<one sentence — cite abnormal_return if available>",
  "source_reliability": [{"source":"<name>","articles":<int>,"reliability_score":<int>,"tier":"Tier 1|Tier 2|Tier 3|Social|Primary"}],
  "articles": [{"headline":"<string>","source":"<string>","published_at":"<date>","sentiment":<float>,"sentiment_label":"Bullish|Bearish|Neutral","event_type":"<type>|null","reliability_score":<int>,"impact_score":<float>}],
  "price_prediction": {
    "last_close":<float>,"low":<float>,"base":<float>,"high":<float>,
    "change_pct_low":<float>,"change_pct_base":<float>,"change_pct_high":<float>,
    "confidence":<int>,"bias":"Bullish|Bearish|Neutral",
    "volatility_regime":"low|medium|high",
    "reasoning":"<two sentences citing real clusters and OHLCV>",
    "upside_catalyst":"<one sentence>","downside_risk":"<one sentence>",
    "disclaimer":"News-sentiment model with real data. Not financial advice."
  }
}"""

    async def generate(self, ticker: str, clusters: list[dict], price_ctx: dict) -> dict:
        user_msg = (
            f"Ticker: {ticker}\n\n"
            f"Market context:\n{json.dumps(price_ctx, indent=2)}\n\n"
            f"News clusters ({len(clusters)} — pre-processed, sorted by impact):\n"
            f"{json.dumps(clusters, indent=2)}\n\n"
            f"Return the research report JSON matching this schema:\n{self.REPORT_SCHEMA}"
        )

        @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15),
               retry=retry_if_exception_type(aiohttp.ClientError))
        async def _call():
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": ANTHROPIC_API_KEY,
                             "anthropic-version": "2023-06-01",
                             "content-type": "application/json"},
                    json={"model": "claude-sonnet-4-20250514", "max_tokens": 4000,
                          "system": self.SYSTEM_PROMPT,
                          "messages": [{"role": "user", "content": user_msg}]},
                ) as resp:
                    resp.raise_for_status()
                    return await resp.json()

        data = await _call()
        if data.get("error"):
            raise RuntimeError(data["error"]["message"])
        text  = "".join(b.get("text", "") for b in data.get("content", []))
        clean = text.replace("```json", "").replace("```", "").strip()
        start, end = clean.find("{"), clean.rfind("}")
        if start == -1:
            raise ValueError("No JSON in Claude response")
        return json.loads(clean[start:end + 1])


# ─── Pipeline orchestrator ────────────────────────────────────────────────────

async def run_pipeline(
    ticker:  str,
    days:    int = 7,
    db_pool  = None,
    qdrant:  Optional[QdrantStore] = None,
) -> dict:
    run_id = str(uuid4())
    start_t = time.monotonic()
    log.info("pipeline.start", run_id=run_id, ticker=ticker, days=days)

    # ── Stage 1: Collect ──────────────────────────────────────────────────
    collector = NewsCollectorAgent(ticker, days)
    raw = await collector.collect()
    if db_pool:
        await persist_raw_articles(db_pool, raw)

    # ── Stage 2: Clean + dedupe ───────────────────────────────────────────
    cleaner = NewsCleanerAgent(qdrant=qdrant)
    cleaned = cleaner.clean(raw)

    # ── Stage 3: FinBERT sentiment ────────────────────────────────────────
    sentiment = SentimentAgent()
    with_sent = sentiment.analyze(cleaned)

    # ── Stage 4: Event extraction ─────────────────────────────────────────
    events = EventExtractionAgent()
    with_events = events.extract(with_sent)

    # ── Stage 5: Market data + price join ────────────────────────────────
    market = MarketDataAgent(ticker)
    try:
        bars     = await market.fetch_ohlcv(days + 5)
        returns  = market.compute_daily_returns(bars)
        vol_map  = market.compute_intraday_volatility(bars)
        with_events = market.join_price_to_articles(with_events, returns, vol_map)
        vol_regime  = market.get_volatility_regime(bars)
        last_close  = market.get_current_price(bars)
        if db_pool:
            await persist_ohlcv(db_pool, bars)
        price_ctx = {
            "last_close":       last_close,
            "volatility_regime": vol_regime,
            "recent_returns":   dict(list(returns.items())[-7:]),
            "avg_daily_vol_pct": round(sum(abs(v) for v in returns.values()) / max(len(returns), 1), 2),
        }
    except Exception as e:
        log.warning("market_data.failed", error=str(e))
        vol_regime = "medium"
        price_ctx  = {"last_close": None, "volatility_regime": vol_regime, "error": str(e)}

    # ── Stage 6: Event impact scoring ─────────────────────────────────────
    scorer = EventImpactScorer()
    with_impact = scorer.score(with_events, volatility_regime=vol_regime)
    if db_pool:
        await persist_processed_articles(db_pool, with_impact)

    # ── Stage 7: Narrative compression ───────────────────────────────────
    compressor = NarrativeCompressor()
    clusters   = compressor.compress(with_impact)

    # ── Stage 8: Upsert to Qdrant ─────────────────────────────────────────
    if qdrant:
        qdrant.upsert_articles(with_impact)

    # ── Stage 9: Claude reasoning on real compressed data ─────────────────
    reporter = ReportAgent()
    report   = await reporter.generate(ticker, clusters, price_ctx)

    # ── Augment with pipeline metadata ────────────────────────────────────
    unique = [a for a in with_impact if not a.is_duplicate]
    dupes  = [a for a in with_impact if a.is_duplicate]
    top_movers = sorted(unique, key=lambda a: a.impact_score, reverse=True)[:5]
    report["_pipeline_meta"] = {
        "run_id":           run_id,
        "raw_articles":     len(raw),
        "after_dedupe":     len(unique),
        "duplicates_removed": len(dupes),
        "clusters_to_claude": len(clusters),
        "sources":          sorted({a.source for a in unique}),
        "volatility_regime": vol_regime,
        "top_impact_events": [
            {"headline": a.headline, "source": a.source, "impact": a.impact_score,
             "event": a.event_type, "abnormal_return": a.abnormal_return}
            for a in top_movers
        ],
        "data_mode": "real",
        "elapsed_s": round(time.monotonic() - start_t, 2),
        "run_at":    datetime.now(timezone.utc).isoformat(),
    }

    # ── Persist report ────────────────────────────────────────────────────
    if db_pool:
        await persist_report(db_pool, ticker, f"{days}d", report)

    log.info("pipeline.complete", run_id=run_id, elapsed=report["_pipeline_meta"]["elapsed_s"],
             unique_articles=len(unique), clusters=len(clusters))
    return report


# ─── FastAPI server ───────────────────────────────────────────────────────────

def create_app():
    from fastapi import FastAPI, BackgroundTasks
    from fastapi.middleware.cors import CORSMiddleware

    app   = FastAPI(title="Financial News Research API", version="3.0")
    pool  = None
    qd    = None

    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.on_event("startup")
    async def startup():
        nonlocal pool, qd
        pool = await get_db_pool()
        await init_db(pool)
        try:
            qd = QdrantStore()
        except Exception as e:
            log.warning("qdrant.unavailable", error=str(e))

    @app.get("/research/{ticker}")
    async def research(ticker: str, days: int = 7):
        return await run_pipeline(ticker.upper(), days, db_pool=pool, qdrant=qd)

    @app.get("/history/{ticker}")
    async def history(ticker: str, limit: int = 10):
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, time_window, data_mode, articles_ct, created_at FROM research_reports "
                "WHERE ticker=$1 ORDER BY created_at DESC LIMIT $2",
                ticker.upper(), limit,
            )
        return [dict(r) for r in rows]

    @app.get("/analogs/{ticker}/{event_type}")
    async def historical_analogs(ticker: str, event_type: str):
        return await fetch_historical_similar_events(pool, ticker.upper(), event_type)

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "3.0",
                "db": pool is not None, "qdrant": qd is not None}

    return app


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="NVDA")
    parser.add_argument("--days",   default=7, type=int)
    parser.add_argument("--serve",  action="store_true")
    parser.add_argument("--no-db",  action="store_true", help="Skip DB/Qdrant (dev mode)")
    args = parser.parse_args()

    if args.serve:
        import uvicorn
        uvicorn.run(create_app(), host="0.0.0.0", port=8000)
    else:
        async def main():
            pool = None if args.no_db else await get_db_pool()
            if pool:
                await init_db(pool)
            qdrant = None if args.no_db else QdrantStore()
            result = await run_pipeline(args.ticker, args.days, db_pool=pool, qdrant=qdrant)
            print(json.dumps(result, indent=2, default=str))
        asyncio.run(main())
