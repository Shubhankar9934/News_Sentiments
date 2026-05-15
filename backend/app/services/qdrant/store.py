"""Qdrant vector store."""

from __future__ import annotations

import hashlib
import uuid

import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, VectorParams

from app.core.config import Settings
from app.services.domain.models import ProcessedArticle

log = structlog.get_logger(__name__)


def _qdrant_point_id(article_id: str) -> str:
    """Qdrant accepts only unsigned integers or UUID strings."""
    try:
        return str(uuid.UUID(article_id))
    except (ValueError, TypeError):
        return str(uuid.UUID(bytes=hashlib.md5(article_id.encode()).digest()))


class QdrantStoreService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        from qdrant_client.models import PointStruct

        self.PointStruct = PointStruct

        existing = [c.name for c in self.client.get_collections().collections]
        if settings.qdrant_collection not in existing:
            self.client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            log.info("qdrant.collection_created", name=settings.qdrant_collection)

    def upsert_articles(self, articles: list[ProcessedArticle]) -> None:
        points = []
        for a in articles:
            if not a.embedding:
                continue
            points.append(
                self.PointStruct(
                    id=_qdrant_point_id(a.id),
                    vector=a.embedding[:384],
                    payload={
                        "article_id": a.id,
                        "ticker": a.ticker,
                        "headline": a.headline,
                        "source": a.source,
                        "published_at": a.published_at.isoformat(),
                        "sentiment": a.sentiment_score,
                        "event_type": a.event_type,
                        "impact_score": a.impact_score,
                    },
                )
            )
        if points:
            self.client.upsert(collection_name=self._settings.qdrant_collection, points=points)
            log.info("qdrant.upserted", count=len(points))

    def search_similar(self, embedding: list[float], ticker: str | None = None, limit: int = 10):
        filt = None
        if ticker:
            filt = Filter(must=[FieldCondition(key="ticker", match=MatchValue(value=ticker))])
        return self.client.search(
            collection_name=self._settings.qdrant_collection,
            query_vector=embedding,
            query_filter=filt,
            limit=limit,
            with_payload=True,
        )

    def find_historical_analogs(self, embedding: list[float], ticker: str, limit: int = 5):
        results = self.search_similar(embedding, ticker=None, limit=limit * 3)
        analogs = [r for r in results if r.payload.get("ticker") == ticker and r.score > 0.85]
        return analogs[:limit]
