"""Hybrid analog matcher combining SQL, Qdrant semantic search, and pattern rules."""

from __future__ import annotations

from typing import Any, Literal

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.repositories.analog_repository import AnalogRepository
from app.services.analogs.patterns import (
    detect_earnings_beat_sell_off,
    detect_sector_rotation,
)
from app.services.qdrant.store import QdrantStoreService

log = structlog.get_logger(__name__)

AnalogMatchReason = Literal[
    "exact_event_type",
    "semantic",
    "earnings_beat_sell_off",
    "sector_rotation",
]

_WEIGHTS: dict[str, float] = {
    "exact_event_type": 0.4,
    "semantic": 0.4,
    "earnings_beat_sell_off": 0.85,
    "sector_rotation": 0.7,
}


def _row_key(r: dict[str, Any]) -> tuple[str, str]:
    head = (r.get("headline") or "").strip().lower()
    pub = r.get("published_at")
    if hasattr(pub, "date"):
        pub_str = pub.date().isoformat()
    else:
        pub_str = (str(pub) if pub else "")[:10]
    return head, pub_str


def _ensure_match_fields(
    row: dict[str, Any], reason: AnalogMatchReason, score: float
) -> dict[str, Any]:
    out = dict(row)
    out.setdefault("match_reason", reason)
    out.setdefault("match_score", round(score, 3))
    return out


class AnalogService:
    """Compose SQL exact-event-type results with semantic and pattern matches."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        qdrant: QdrantStoreService | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._qdrant = qdrant
        self._sql = AnalogRepository(session)

    async def fetch_analogs(
        self,
        ticker: str,
        event_type: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Return the top ``limit`` analogs ranked by a blended score."""
        ticker = (ticker or "").upper().strip()
        candidates: dict[tuple[str, str], dict[str, Any]] = {}

        sql_rows = await self._sql.fetch_similar_events(ticker, event_type, limit=limit * 2)
        for r in sql_rows:
            row = _ensure_match_fields(r, "exact_event_type", _WEIGHTS["exact_event_type"])
            candidates[_row_key(row)] = row

        if self._settings.analog_pattern_enabled:
            extra_rows = await self._broader_corpus(ticker, limit=limit * 4)
            for r in detect_earnings_beat_sell_off(extra_rows):
                key = _row_key(r)
                existing = candidates.get(key)
                if not existing or r["match_score"] > existing.get("match_score", 0):
                    candidates[key] = r
            for r in detect_sector_rotation(extra_rows):
                key = _row_key(r)
                existing = candidates.get(key)
                if not existing or r["match_score"] > existing.get("match_score", 0):
                    candidates[key] = r

        if self._settings.analog_semantic_enabled and self._qdrant is not None:
            try:
                semantic_rows = await self._semantic_candidates(ticker, limit=limit * 3)
                for r in semantic_rows:
                    key = _row_key(r)
                    if key in candidates:
                        # Boost score when both SQL and semantic agree on this row.
                        candidates[key]["match_score"] = round(
                            min(1.0, candidates[key].get("match_score", 0) + 0.15), 3
                        )
                        candidates[key].setdefault("match_reason", "semantic")
                    else:
                        candidates[key] = r
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("analog.semantic_failed", error=str(exc))

        ranked = sorted(
            candidates.values(),
            key=lambda r: r.get("match_score", 0),
            reverse=True,
        )
        return ranked[:limit]

    async def _broader_corpus(self, ticker: str, limit: int) -> list[dict[str, Any]]:
        """Pull a wider slice of historical articles to feed pattern detectors."""
        q = text(
            """
            SELECT p.headline, p.published_at, p.sentiment_score, p.impact_score,
                   o.close, o.volume
            FROM processed_articles p
            LEFT JOIN ohlcv_bars o ON o.ticker = p.ticker
                AND o.timestamp::date = p.published_at::date
            WHERE p.ticker = :ticker
            ORDER BY p.impact_score DESC NULLS LAST, p.published_at DESC
            LIMIT :limit
            """
        )
        result = await self._session.execute(q, {"ticker": ticker, "limit": limit})
        return [dict(row._mapping) for row in result.fetchall()]

    async def _semantic_candidates(self, ticker: str, limit: int) -> list[dict[str, Any]]:
        """Ask Qdrant for high-cosine neighbours; join OHLCV from the SQL side.

        We don't have a query embedding here (no in-flight article), so we use
        the most recent high-impact embedding for this ticker as the proxy.
        """
        if self._qdrant is None:
            return []
        seed_q = text(
            """
            SELECT id FROM processed_articles
            WHERE ticker = :ticker AND impact_score IS NOT NULL
            ORDER BY impact_score DESC NULLS LAST, published_at DESC
            LIMIT 1
            """
        )
        result = await self._session.execute(seed_q, {"ticker": ticker})
        row = result.first()
        if row is None:
            return []
        seed_id = str(row[0])

        # Pull the seed embedding via the Qdrant payload search (best-effort).
        try:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            seed_hits = self._qdrant.client.scroll(
                collection_name=self._settings.qdrant_collection,
                scroll_filter=Filter(
                    must=[FieldCondition(key="article_id", match=MatchValue(value=seed_id))]
                ),
                limit=1,
                with_vectors=True,
            )
            points = seed_hits[0] if seed_hits else []
            if not points:
                return []
            seed_vec = points[0].vector
        except Exception:  # pragma: no cover - resilient against client API drift
            return []

        try:
            neighbors = self._qdrant.find_historical_analogs(seed_vec, ticker, limit=limit)
        except Exception:  # pragma: no cover
            return []

        out: list[dict[str, Any]] = []
        for n in neighbors:
            payload = n.payload or {}
            if payload.get("article_id") == seed_id:
                continue
            out.append(
                _ensure_match_fields(
                    {
                        "headline": payload.get("headline"),
                        "published_at": payload.get("published_at"),
                        "sentiment_score": payload.get("sentiment"),
                        "impact_score": payload.get("impact_score"),
                        "close": None,
                        "volume": None,
                    },
                    "semantic",
                    float(n.score) if hasattr(n, "score") else _WEIGHTS["semantic"],
                )
            )
        return out
