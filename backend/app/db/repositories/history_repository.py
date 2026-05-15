"""Research report history."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.tables import ResearchReportModel


class HistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_ticker(self, ticker: str, limit: int = 10) -> list[dict[str, Any]]:
        stmt = (
            select(ResearchReportModel)
            .where(ResearchReportModel.ticker == ticker)
            .order_by(ResearchReportModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "id": str(r.id),
                    "time_window": r.time_window,
                    "data_mode": r.data_mode,
                    "articles_ct": r.articles_ct,
                    "created_at": r.created_at,
                    "report_json": r.report_json,
                }
            )
        return out
