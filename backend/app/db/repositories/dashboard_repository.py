"""Read/write layer for the Reverse BWB Intelligence Dashboard tables.

Three writes per successful refresh, in one DB session:

    1. UPSERT ticker_reports by ticker (latest snapshot)
    2. UPSERT ticker_reverse_bwb_summary by ticker
    3. DELETE FROM ticker_option_opportunities WHERE ticker = $1, then INSERT

For failures, ``mark_failed`` sets ``status='failed'`` on ticker_reports and
removes the stale summary + opportunities so the dashboard cleanly renders a
"Data unavailable" empty state instead of showing yesterday's data.

Reads are served via ``list_dashboard_cards`` (LEFT JOIN across all three
tables, returning a row for every watchlist ticker — missing rows become
``status='pending'`` placeholders so the grid layout is stable).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.tables import (
    TickerOptionOpportunityModel,
    TickerReportModel,
    TickerReverseBwbSummaryModel,
)
from app.services.dashboard.schemas import (
    DashboardTickerCard,
    DashboardTickerReportResponse,
    OptionOpportunities,
    OptionOpportunity,
    PriceSnapshot,
    ReverseBwbSummary,
    empty_card,
    normalize_liquidity,
)
from app.services.dashboard.watchlist import (
    WATCHLIST_COMPANY_BY_SYMBOL,
    WATCHLIST_TIERS,
    WATCHLIST_TIER_KEY_BY_SYMBOL,
)


def _json_safe(payload: Any) -> Any:
    """Deep-coerce datetimes/Decimals/etc. to JSON-friendly primitives."""

    return json.loads(json.dumps(payload, default=str))


def _extract_price_snapshot(report_json: dict[str, Any] | None) -> PriceSnapshot | None:
    if not report_json:
        return None
    meta = report_json.get("_pipeline_meta") or {}
    snap = meta.get("price_snapshot") or {}
    last_close = snap.get("last_close")
    change_pct = snap.get("daily_change_pct") or snap.get("session_change_pct")
    if last_close is None and change_pct is None:
        return None
    return PriceSnapshot(
        price=float(last_close) if last_close is not None else None,
        daily_change_pct=float(change_pct) if change_pct is not None else None,
        as_of=snap.get("as_of"),
        source=snap.get("source") or "pipeline",
    )


def _summary_model_to_schema(row: TickerReverseBwbSummaryModel, ticker: str) -> ReverseBwbSummary:
    """Read-path projection.

    Stored rows may predate the Enter/Wait/Avoid migration. We run every
    string-typed field through ``normalize_summary_dict`` before
    re-validating so legacy ``SAFE``/``Cheap``/``Extreme``/``Mixed``
    values round-trip into the new vocabulary without breaking the
    grid.
    """

    raw: dict[str, Any] = {
        "ticker": ticker,
        "decision": row.decision,
        "credit_safety_score": row.credit_safety_score,
        "risk": row.risk,
        "confidence": row.confidence,
        "today_outlook": row.today_outlook,
        "next_3d_outlook": row.next_3d_outlook,
        "chance_up_2_3_pct": row.chance_up_2_3_pct,
        "chance_down_2_3_pct": row.chance_down_2_3_pct,
        "expected_range_today": row.expected_range_today,
        "expected_range_next_3d": row.expected_range_next_3d,
        "danger_zone": row.danger_zone,
        "pin_risk": row.pin_risk,
        "event_risk": row.event_risk,
        "iv_quality": row.iv_quality,
        "liquidity": row.liquidity,
        "actual_dynamics_summary": list(row.actual_dynamics_summary or []),
    }
    from app.services.dashboard.schemas import normalize_summary_dict

    return ReverseBwbSummary.model_validate(normalize_summary_dict(raw))


def _opportunity_model_to_schema(row: TickerOptionOpportunityModel) -> OptionOpportunity:
    return OptionOpportunity(
        combo=row.combo,
        expiry=row.expiry,
        premium=row.premium,
        margin=row.margin,
        liquidity=normalize_liquidity(row.liquidity),
    )


class DashboardRepository:
    """All dashboard table I/O. One instance per logical refresh / request."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ----------------------- write path -----------------------

    async def save_snapshot(
        self,
        ticker: str,
        report_json: dict[str, Any],
        summary: ReverseBwbSummary,
        opportunities: OptionOpportunities,
        *,
        research_report_id: uuid.UUID | None = None,
        assessment_layer: dict[str, Any] | None = None,
        council_layer: dict[str, Any] | None = None,
        explainability: dict[str, Any] | None = None,
    ) -> uuid.UUID:
        """Persist a full successful refresh for one ticker.

        Single session, three statements: upsert ticker_reports, upsert
        ticker_reverse_bwb_summary, truncate + insert option opportunities.
        Returns the upserted ``ticker_reports.id`` so callers can correlate.
        """

        ticker = ticker.upper()
        now = datetime.now(UTC)
        safe_report = _json_safe(report_json)

        report_stmt = (
            insert(TickerReportModel)
            .values(
                ticker=ticker,
                research_report_id=research_report_id,
                status="completed",
                error_message=None,
                report_json=safe_report,
                generated_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["ticker"],
                set_={
                    "research_report_id": research_report_id,
                    "status": "completed",
                    "error_message": None,
                    "report_json": safe_report,
                    "generated_at": now,
                    "updated_at": now,
                },
            )
            .returning(TickerReportModel.id)
        )
        result = await self._session.execute(report_stmt)
        ticker_report_id: uuid.UUID = result.scalar_one()

        summary_payload = dict(
            ticker=ticker,
            ticker_report_id=ticker_report_id,
            decision=summary.decision,
            credit_safety_score=summary.credit_safety_score,
            risk=summary.risk,
            confidence=summary.confidence,
            today_outlook=summary.today_outlook,
            next_3d_outlook=summary.next_3d_outlook,
            chance_up_2_3_pct=summary.chance_up_2_3_pct,
            chance_down_2_3_pct=summary.chance_down_2_3_pct,
            expected_range_today=summary.expected_range_today.model_dump(),
            expected_range_next_3d=summary.expected_range_next_3d.model_dump(),
            danger_zone=summary.danger_zone,
            pin_risk=summary.pin_risk,
            event_risk=summary.event_risk,
            iv_quality=summary.iv_quality,
            liquidity=summary.liquidity,
            actual_dynamics_summary=list(summary.actual_dynamics_summary),
            assessment_layer=_json_safe(assessment_layer) if assessment_layer else None,
            council_layer=_json_safe(council_layer) if council_layer else None,
            explainability=_json_safe(explainability) if explainability else None,
            updated_at=now,
        )

        summary_stmt = (
            insert(TickerReverseBwbSummaryModel)
            .values(**summary_payload)
            .on_conflict_do_update(
                index_elements=["ticker"],
                set_={k: v for k, v in summary_payload.items() if k != "ticker"},
            )
        )
        await self._session.execute(summary_stmt)

        # Truncate-by-ticker + insert (placeholder generator returns 2+2 rows).
        await self._session.execute(
            delete(TickerOptionOpportunityModel).where(
                TickerOptionOpportunityModel.ticker == ticker
            )
        )

        rows_to_insert: list[dict[str, Any]] = []
        for rank, opp in enumerate(opportunities.calls):
            rows_to_insert.append(
                {
                    "ticker": ticker,
                    "ticker_report_id": ticker_report_id,
                    "option_type": "CALL",
                    "rank": rank,
                    "combo": opp.combo,
                    "expiry": opp.expiry,
                    "premium": opp.premium,
                    "margin": opp.margin,
                    "liquidity": opp.liquidity,
                }
            )
        for rank, opp in enumerate(opportunities.puts):
            rows_to_insert.append(
                {
                    "ticker": ticker,
                    "ticker_report_id": ticker_report_id,
                    "option_type": "PUT",
                    "rank": rank,
                    "combo": opp.combo,
                    "expiry": opp.expiry,
                    "premium": opp.premium,
                    "margin": opp.margin,
                    "liquidity": opp.liquidity,
                }
            )
        if rows_to_insert:
            await self._session.execute(
                insert(TickerOptionOpportunityModel),
                rows_to_insert,
            )

        await self._session.commit()
        return ticker_report_id

    async def patch_reverse_bwb_decision(
        self,
        ticker: str,
        mapped_decision: str,
        *,
        council_decision: str | None = None,
    ) -> bool:
        """Update dashboard decision after a non-batch council completes.

        The watchlist batch now writes the council-sourced decision
        synchronously via ``save_snapshot``. This path remains for the
        legacy async ``runner.py`` flow used by ``/research/{ticker}``.
        It is a no-op when the row already stores a row whose
        ``council_layer`` is populated — that means the batch already
        wrote the authoritative council decision and we must not let a
        stale follow-up overwrite it.
        """

        ticker = ticker.upper()
        summary = await self._session.scalar(
            select(TickerReverseBwbSummaryModel).where(
                TickerReverseBwbSummaryModel.ticker == ticker
            )
        )
        if summary is None:
            return False

        if summary.council_layer is not None:
            # Synchronous council write already wins.
            return False

        summary.decision = mapped_decision
        summary.updated_at = datetime.now(UTC)

        report = await self._session.scalar(
            select(TickerReportModel).where(TickerReportModel.ticker == ticker)
        )
        if report and report.report_json:
            payload = dict(report.report_json)
            dil = dict(payload.get("deliberation_layer") or {})
            if council_decision:
                dil["council_decision_raw"] = council_decision
            dil["mapped_decision"] = mapped_decision
            payload["deliberation_layer"] = dil
            report.report_json = _json_safe(payload)
            report.updated_at = datetime.now(UTC)

        await self._session.commit()
        return True

    async def mark_failed(self, ticker: str, error_message: str) -> None:
        """Record a failed refresh and clear stale data for this ticker."""

        ticker = ticker.upper()
        now = datetime.now(UTC)
        message = (error_message or "unknown error")[:2000]

        stmt = (
            insert(TickerReportModel)
            .values(
                ticker=ticker,
                research_report_id=None,
                status="failed",
                error_message=message,
                report_json=None,
                generated_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["ticker"],
                set_={
                    "status": "failed",
                    "error_message": message,
                    "updated_at": now,
                    # Keep prior report_json so the empty state still has
                    # generated_at metadata if needed.
                },
            )
        )
        await self._session.execute(stmt)
        await self._session.execute(
            delete(TickerReverseBwbSummaryModel).where(
                TickerReverseBwbSummaryModel.ticker == ticker
            )
        )
        await self._session.execute(
            delete(TickerOptionOpportunityModel).where(
                TickerOptionOpportunityModel.ticker == ticker
            )
        )
        await self._session.commit()

    # ----------------------- read path -----------------------

    async def list_dashboard_cards(self) -> list[DashboardTickerCard]:
        """One card per watchlist ticker, in canonical tier/order.

        Tickers without a persisted row return ``status='pending'`` so the
        grid layout stays stable on first boot.
        """

        report_rows = (
            await self._session.execute(select(TickerReportModel))
        ).scalars().all()
        summary_rows = (
            await self._session.execute(select(TickerReverseBwbSummaryModel))
        ).scalars().all()
        opp_rows = (
            await self._session.execute(select(TickerOptionOpportunityModel))
        ).scalars().all()

        reports_by_ticker: dict[str, TickerReportModel] = {r.ticker: r for r in report_rows}
        summaries_by_ticker: dict[str, TickerReverseBwbSummaryModel] = {
            r.ticker: r for r in summary_rows
        }
        opps_by_ticker: dict[str, list[TickerOptionOpportunityModel]] = {}
        for row in opp_rows:
            opps_by_ticker.setdefault(row.ticker, []).append(row)

        cards: list[DashboardTickerCard] = []
        for tier in WATCHLIST_TIERS:
            for entry in tier.tickers:
                cards.append(
                    self._build_card(
                        entry.symbol,
                        entry.company,
                        tier.key,
                        reports_by_ticker.get(entry.symbol),
                        summaries_by_ticker.get(entry.symbol),
                        opps_by_ticker.get(entry.symbol, []),
                    )
                )
        return cards

    async def get_dashboard_card(self, ticker: str) -> DashboardTickerCard | None:
        ticker = ticker.upper()
        if ticker not in WATCHLIST_COMPANY_BY_SYMBOL:
            return None
        report = await self._session.scalar(
            select(TickerReportModel).where(TickerReportModel.ticker == ticker)
        )
        summary = await self._session.scalar(
            select(TickerReverseBwbSummaryModel).where(
                TickerReverseBwbSummaryModel.ticker == ticker
            )
        )
        opps = (
            await self._session.execute(
                select(TickerOptionOpportunityModel)
                .where(TickerOptionOpportunityModel.ticker == ticker)
                .order_by(
                    TickerOptionOpportunityModel.option_type,
                    TickerOptionOpportunityModel.rank,
                )
            )
        ).scalars().all()
        return self._build_card(
            ticker,
            WATCHLIST_COMPANY_BY_SYMBOL[ticker],
            WATCHLIST_TIER_KEY_BY_SYMBOL[ticker],
            report,
            summary,
            list(opps),
        )

    async def get_ticker_report(self, ticker: str) -> DashboardTickerReportResponse | None:
        """Return the full ``ticker_reports`` snapshot for one watchlist ticker."""

        ticker = ticker.upper()
        if ticker not in WATCHLIST_COMPANY_BY_SYMBOL:
            return None

        report = await self._session.scalar(
            select(TickerReportModel).where(TickerReportModel.ticker == ticker)
        )
        if report is None or report.report_json is None:
            return None

        status_literal = "failed" if report.status == "failed" else "completed"
        return DashboardTickerReportResponse(
            ticker=ticker,
            status=status_literal,  # type: ignore[arg-type]
            research_report_id=(
                str(report.research_report_id) if report.research_report_id else None
            ),
            generated_at=report.generated_at,
            report_json=dict(report.report_json),
        )

    def _build_card(
        self,
        ticker: str,
        company_name: str,
        tier_key: str,
        report: TickerReportModel | None,
        summary: TickerReverseBwbSummaryModel | None,
        opp_rows: list[TickerOptionOpportunityModel],
    ) -> DashboardTickerCard:
        if report is None:
            return empty_card(ticker, company_name, tier_key)

        calls: list[OptionOpportunity] = []
        puts: list[OptionOpportunity] = []
        for row in sorted(opp_rows, key=lambda r: (r.option_type, r.rank)):
            schema = _opportunity_model_to_schema(row)
            if row.option_type.upper() == "CALL":
                calls.append(schema)
            else:
                puts.append(schema)

        status_literal = "failed" if report.status == "failed" else (
            "completed" if summary is not None else "pending"
        )

        return DashboardTickerCard(
            ticker=ticker,
            company_name=company_name,
            tier_key=tier_key,
            status=status_literal,  # type: ignore[arg-type]
            generated_at=report.generated_at,
            price_snapshot=_extract_price_snapshot(report.report_json),
            reverse_bwb=_summary_model_to_schema(summary, ticker) if summary else None,
            opportunities=OptionOpportunities(calls=calls, puts=puts) if (calls or puts) else None,
            report_id=str(report.research_report_id) if report.research_report_id else None,
            error_message=report.error_message,
        )
