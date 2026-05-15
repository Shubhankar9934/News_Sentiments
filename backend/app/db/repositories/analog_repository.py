"""Historical analog queries (SQL, legacy-compatible)."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AnalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def fetch_similar_events(
        self, ticker: str, event_type: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        q = text("""
            SELECT p.headline, p.published_at, p.sentiment_score, p.impact_score, o.close, o.volume
            FROM processed_articles p
            LEFT JOIN ohlcv_bars o ON o.ticker = p.ticker
                AND o.timestamp::date = p.published_at::date
            WHERE p.ticker = :ticker AND p.event_type = :event_type
            ORDER BY p.impact_score DESC NULLS LAST, p.published_at DESC
            LIMIT :limit
            """)
        result = await self._session.execute(
            q, {"ticker": ticker, "event_type": event_type, "limit": limit}
        )
        return [dict(row._mapping) for row in result.fetchall()]
