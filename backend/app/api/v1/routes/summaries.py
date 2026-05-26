"""Lightweight grid-summaries endpoint.

Layer-1 dashboard cards consume a slim projection of the latest persisted
report per ticker. This avoids shipping the full ``report_json`` (which can
be 50-200 kB after PR-A1 + DIL) for the twelve cards on grid mount.

The shape mirrors what the front-end ``TickerCard`` renders directly:

```
[
  {
    "ticker": "NVDA",
    "report_id": "uuid" | null,
    "deliberation_status": "complete" | "pending" | ... | null,
    "last_close": 124.5,
    "session_change_pct": 1.25,
    "executive_summary": ExecutiveSummary | null,
    "last_run_at": "2026-05-24T14:33:00Z" | null
  },
  ...
]
```
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import load_only

from app.core.config import get_settings
from app.core.dependencies import SessionDep
from app.core.rate_limit import limiter
from app.db.models.tables import ResearchReportModel
from app.services.summary import extract_executive_summary

router = APIRouter()

MAX_TICKERS = 24


def _project_row(row: ResearchReportModel) -> dict[str, Any]:
    report = row.report_json or {}
    meta = report.get("_pipeline_meta") or {}
    snap = meta.get("price_snapshot") or {}
    deliberation = report.get("deliberation_layer") or {}

    summary = report.get("executive_summary")
    if not summary:
        # Older reports persisted before this feature: derive on read so the
        # grid stays populated without forcing a re-run.
        try:
            summary = extract_executive_summary(report).model_dump()
        except Exception:
            summary = None

    return {
        "ticker": row.ticker.upper(),
        "report_id": str(row.id),
        "deliberation_status": deliberation.get("status"),
        "last_close": snap.get("last_close"),
        "session_change_pct": snap.get("last_session_change_pct"),
        "executive_summary": summary,
        "last_run_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/summaries")
@limiter.limit(get_settings().rate_limit_summaries)
async def get_summaries(
    request: Request,
    session: SessionDep,
    tickers: str = Query(..., description="Comma-separated tickers, e.g. SPY,QQQ,NVDA"),
) -> list[dict[str, Any]]:
    """Return slim per-ticker rows for the watchlist grid in a single hop.

    Tickers without any persisted report come back with all-null fields so
    the front-end can render IDLE cards without a second probe.
    """
    parsed = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not parsed:
        raise HTTPException(status_code=400, detail="tickers must be non-empty")
    if len(parsed) > MAX_TICKERS:
        raise HTTPException(
            status_code=400,
            detail=f"max {MAX_TICKERS} tickers per request (received {len(parsed)})",
        )

    seen: set[str] = set()
    ordered: list[str] = []
    for t in parsed:
        if t in seen:
            continue
        seen.add(t)
        ordered.append(t)

    # Pull every report for the requested tickers ordered by recency. The
    # existing ``idx_reports_ticker (ticker, created_at DESC)`` index makes
    # this a tight key-only scan; with at most ~24 tickers the result set is
    # bounded by the per-ticker cap.
    stmt = (
        select(ResearchReportModel)
        .where(ResearchReportModel.ticker.in_(ordered))
        .order_by(
            ResearchReportModel.ticker.asc(),
            ResearchReportModel.created_at.desc(),
        )
        .options(
            load_only(
                ResearchReportModel.id,
                ResearchReportModel.ticker,
                ResearchReportModel.report_json,
                ResearchReportModel.created_at,
            )
        )
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    latest_per_ticker: dict[str, ResearchReportModel] = {}
    for row in rows:
        key = row.ticker.upper()
        if key not in latest_per_ticker:
            latest_per_ticker[key] = row

    return [
        _project_row(latest_per_ticker[t])
        if t in latest_per_ticker
        else {
            "ticker": t,
            "report_id": None,
            "deliberation_status": None,
            "last_close": None,
            "session_change_pct": None,
            "executive_summary": None,
            "last_run_at": None,
        }
        for t in ordered
    ]
