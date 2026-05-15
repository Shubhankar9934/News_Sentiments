"""Write path for pipeline outputs."""

import json
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.tables import (
    OhlcvBarModel,
    ProcessedArticleModel,
    RawArticleModel,
    ResearchReportModel,
)
from app.services.domain.models import OHLCVBar, ProcessedArticle, RawArticle


class PersistenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def persist_raw_articles(self, articles: list[RawArticle]) -> None:
        if not articles:
            return
        for a in articles:
            stmt = (
                insert(RawArticleModel)
                .values(
                    external_id=a.id,
                    ticker=a.ticker,
                    headline=a.headline,
                    content=a.content,
                    source=a.source,
                    url=a.url,
                    published_at=a.published_at,
                    raw_json=a.raw_json,
                )
                .on_conflict_do_nothing(index_elements=["external_id"])
            )
            await self._session.execute(stmt)
        await self._session.commit()

    async def persist_processed_articles(self, articles: list[ProcessedArticle]) -> None:
        if not articles:
            return
        for a in articles:
            row = ProcessedArticleModel(
                raw_article_id=None,
                ticker=a.ticker,
                headline=a.headline,
                source=a.source,
                published_at=a.published_at,
                sentiment_score=a.sentiment_score,
                sentiment_label=a.sentiment_label,
                event_type=a.event_type,
                reliability_score=a.reliability_score,
                impact_score=a.impact_score,
                abnormal_return=a.abnormal_return,
                is_duplicate=a.is_duplicate,
                cluster_id=a.cluster_id,
            )
            self._session.add(row)
        await self._session.commit()

    async def persist_ohlcv(self, bars: list[OHLCVBar]) -> None:
        if not bars:
            return
        for b in bars:
            stmt = insert(OhlcvBarModel).values(
                ticker=b.ticker,
                timestamp=b.timestamp,
                timeframe="1d",
                open=b.open,
                high=b.high,
                low=b.low,
                close=b.close,
                volume=b.volume,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["ticker", "timestamp", "timeframe"],
                set_={
                    "open": stmt.excluded.open,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "close": stmt.excluded.close,
                    "volume": stmt.excluded.volume,
                },
            )
            await self._session.execute(stmt)
        await self._session.commit()

    async def persist_report(self, ticker: str, window: str, report: dict[str, Any]) -> None:
        row = ResearchReportModel(
            ticker=ticker,
            time_window=window,
            report_json=json.loads(json.dumps(report, default=str)),
            data_mode=report.get("data_mode"),
            articles_ct=report.get("articles_analyzed", 0),
        )
        self._session.add(row)
        await self._session.commit()
