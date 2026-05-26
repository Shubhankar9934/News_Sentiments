"""Persistence layer for the live IBKR market-data tables.

Three tables, three write paths:

    1. ``ticker_market_data``                       — UPSERT keyed by ticker.
    2. ``ticker_live_option_opportunities``         — DELETE WHERE ticker=?
                                                       AND side=? then INSERT
                                                       (atomic per side).
    3. ``ticker_option_opportunity_history``        — APPEND ONLY. Every
                                                       generated row is
                                                       written here with
                                                       its ``opportunity_version``
                                                       UUID and the trading
                                                       ``snapshot_date``.

This repository never touches ``ticker_reports``,
``ticker_reverse_bwb_summary`` or ``ticker_option_opportunities`` — that is
the strict separation between live data and frozen analysis snapshots.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import delete, desc, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.tables import (
    TickerLiveOptionOpportunityModel,
    TickerMarketDataModel,
    TickerOptionOpportunityHistoryModel,
)
from app.services.market_data.schemas import (
    DashboardLiveBundle,
    DashboardLiveTickerEntry,
    FeedStatus,
    LiveOpportunity,
    LiveOpportunityBundle,
    LiveQuote,
    OpportunityHistoryEntry,
    SideLiteral,
)


def _to_decimal(value: float | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(repr(float(value)))


def _to_float(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _to_int(value: int | None) -> int | None:
    if value is None:
        return None
    return int(value)


def _bucket_feed_status(updated_at: datetime | None, stale_threshold_s: int) -> FeedStatus:
    """Classify a stored row's freshness for read-side responses."""
    if updated_at is None:
        return "unavailable"
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    age = datetime.now(UTC) - updated_at
    if age > timedelta(seconds=stale_threshold_s * 6):
        return "disconnected"
    if age > timedelta(seconds=stale_threshold_s):
        return "stale"
    return "live"


def _live_opp_row_payload(
    opp: LiveOpportunity,
    *,
    fallback_updated_at: datetime,
) -> dict[str, object]:
    """Serialize a LiveOpportunity into a dict ready for INSERT."""

    return {
        "ticker": opp.ticker.upper(),
        "side": opp.side,
        "rank": int(opp.rank),
        "combo": opp.combo,
        "strike_long_wing_a": _to_decimal(opp.strike_long_wing_a),
        "strike_short_body": _to_decimal(opp.strike_short_body),
        "strike_long_wing_b": _to_decimal(opp.strike_long_wing_b),
        "expiration": opp.expiration,
        "expiry_days": _to_int(opp.expiry_days),
        "delta_pct": _to_decimal(opp.delta_pct),
        "premium": _to_decimal(opp.premium),
        "init_margin": _to_decimal(opp.init_margin),
        "maint_margin": _to_decimal(opp.maint_margin),
        "init_margin_source": opp.init_margin_source,
        "liquidity": int(opp.liquidity),
        "minimum_open_interest": _to_int(opp.minimum_open_interest),
        "minimum_volume": _to_int(opp.minimum_volume),
        "oi_leg1": _to_int(opp.oi_leg1),
        "oi_leg2": _to_int(opp.oi_leg2),
        "oi_leg3": _to_int(opp.oi_leg3),
        "vol_leg1": _to_int(opp.vol_leg1),
        "vol_leg2": _to_int(opp.vol_leg2),
        "vol_leg3": _to_int(opp.vol_leg3),
        "iv_leg1": _to_decimal(opp.iv_leg1),
        "iv_leg2": _to_decimal(opp.iv_leg2),
        "iv_leg3": _to_decimal(opp.iv_leg3),
        "mid_leg1": _to_decimal(opp.mid_leg1),
        "mid_leg2": _to_decimal(opp.mid_leg2),
        "mid_leg3": _to_decimal(opp.mid_leg3),
        "credit_efficiency": _to_decimal(opp.credit_efficiency),
        "ranking_score": _to_decimal(opp.ranking_score),
        "underlying_price": _to_decimal(opp.underlying_price),
        "iv": _to_decimal(opp.iv),
        "opportunity_version": opp.opportunity_version,
        # Legacy back-compat fields, populated from new equivalents.
        "oi_min": _to_int(opp.minimum_open_interest),
        "vol_min": _to_int(opp.minimum_volume),
        "spread_pct": None,
        "generated_at": opp.generated_at or fallback_updated_at,
        "updated_at": opp.updated_at or fallback_updated_at,
    }


def _history_row_payload(
    opp: LiveOpportunity,
    *,
    fallback_updated_at: datetime,
) -> dict[str, object]:
    """Serialize a LiveOpportunity for the append-only history table."""

    generated = opp.generated_at or fallback_updated_at
    snapshot_date = generated.date() if isinstance(generated, datetime) else None
    return {
        "ticker": opp.ticker.upper(),
        "side": opp.side,
        "combo": opp.combo,
        "strike_long_wing_a": _to_decimal(opp.strike_long_wing_a) or Decimal("0"),
        "strike_short_body": _to_decimal(opp.strike_short_body) or Decimal("0"),
        "strike_long_wing_b": _to_decimal(opp.strike_long_wing_b) or Decimal("0"),
        "expiration": opp.expiration,
        "expiry_days": int(opp.expiry_days or 0),
        "delta_pct": _to_decimal(opp.delta_pct),
        "premium": _to_decimal(opp.premium),
        "init_margin": _to_decimal(opp.init_margin),
        "maint_margin": _to_decimal(opp.maint_margin),
        "init_margin_source": opp.init_margin_source,
        "liquidity": int(opp.liquidity),
        "minimum_open_interest": _to_int(opp.minimum_open_interest),
        "minimum_volume": _to_int(opp.minimum_volume),
        "oi_leg1": _to_int(opp.oi_leg1),
        "oi_leg2": _to_int(opp.oi_leg2),
        "oi_leg3": _to_int(opp.oi_leg3),
        "vol_leg1": _to_int(opp.vol_leg1),
        "vol_leg2": _to_int(opp.vol_leg2),
        "vol_leg3": _to_int(opp.vol_leg3),
        "iv_leg1": _to_decimal(opp.iv_leg1),
        "iv_leg2": _to_decimal(opp.iv_leg2),
        "iv_leg3": _to_decimal(opp.iv_leg3),
        "mid_leg1": _to_decimal(opp.mid_leg1),
        "mid_leg2": _to_decimal(opp.mid_leg2),
        "mid_leg3": _to_decimal(opp.mid_leg3),
        "credit_efficiency": _to_decimal(opp.credit_efficiency),
        "ranking_score": _to_decimal(opp.ranking_score),
        "underlying_price": _to_decimal(opp.underlying_price),
        "iv": _to_decimal(opp.iv),
        "opportunity_version": opp.opportunity_version,
        "generated_at": generated,
        "snapshot_date": snapshot_date,
    }


def _row_to_live_opp(row: TickerLiveOptionOpportunityModel) -> LiveOpportunity:
    return LiveOpportunity(
        ticker=row.ticker,
        side=row.side,  # type: ignore[arg-type]
        rank=int(row.rank or 0),
        combo=row.combo,
        strike_long_wing_a=_to_float(row.strike_long_wing_a),
        strike_short_body=_to_float(row.strike_short_body),
        strike_long_wing_b=_to_float(row.strike_long_wing_b),
        expiration=row.expiration,
        expiry_days=row.expiry_days,
        delta_pct=_to_float(row.delta_pct),
        premium=_to_float(row.premium) or 0.0,
        init_margin=_to_float(row.init_margin),
        maint_margin=_to_float(row.maint_margin),
        init_margin_source=(row.init_margin_source or "deterministic"),  # type: ignore[arg-type]
        liquidity=int(row.liquidity or 0),
        minimum_open_interest=row.minimum_open_interest,
        minimum_volume=row.minimum_volume,
        oi_leg1=row.oi_leg1,
        oi_leg2=row.oi_leg2,
        oi_leg3=row.oi_leg3,
        vol_leg1=row.vol_leg1,
        vol_leg2=row.vol_leg2,
        vol_leg3=row.vol_leg3,
        iv_leg1=_to_float(row.iv_leg1),
        iv_leg2=_to_float(row.iv_leg2),
        iv_leg3=_to_float(row.iv_leg3),
        mid_leg1=_to_float(row.mid_leg1),
        mid_leg2=_to_float(row.mid_leg2),
        mid_leg3=_to_float(row.mid_leg3),
        credit_efficiency=_to_float(row.credit_efficiency),
        ranking_score=_to_float(row.ranking_score),
        underlying_price=_to_float(row.underlying_price),
        iv=_to_float(row.iv),
        opportunity_version=row.opportunity_version,
        generated_at=row.generated_at,
        updated_at=row.updated_at,
    )


class MarketDataRepository:
    """All live-data table I/O. One instance per logical operation."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ----------------------------------------------------------------- writes
    async def upsert_quote(self, quote: LiveQuote) -> None:
        """UPSERT a single ticker_market_data row."""
        ticker = quote.ticker.upper()
        now = quote.updated_at or datetime.now(UTC)

        payload = {
            "ticker": ticker,
            "last_price": _to_decimal(quote.last_price),
            "bid": _to_decimal(quote.bid),
            "ask": _to_decimal(quote.ask),
            "change_abs": _to_decimal(quote.change_abs),
            "change_pct": _to_decimal(quote.change_pct),
            "volume": _to_int(quote.volume),
            "prev_close": _to_decimal(quote.prev_close),
            "feed_status": quote.feed_status,
            "updated_at": now,
        }

        stmt = (
            insert(TickerMarketDataModel)
            .values(**payload)
            .on_conflict_do_update(
                index_elements=["ticker"],
                set_={k: v for k, v in payload.items() if k != "ticker"},
            )
        )
        await self._session.execute(stmt)

    async def upsert_quotes_bulk(self, quotes: Iterable[LiveQuote]) -> int:
        """Batched UPSERT — used by the price loop's debounced flush."""
        rows = list(quotes)
        if not rows:
            return 0
        for q in rows:
            await self.upsert_quote(q)
        await self._session.commit()
        return len(rows)

    async def replace_opportunities(
        self,
        ticker: str,
        side: SideLiteral,
        opportunities: list[LiveOpportunity],
    ) -> None:
        """Atomic per-side refresh: DELETE then INSERT in one transaction.

        Caller is responsible for committing — typically the worker calls
        ``replace_opportunities("SPY", "call", ...)`` then
        ``replace_opportunities("SPY", "put", ...)`` and commits once for
        the whole ticker so calls and puts always land together.
        """
        ticker_upper = ticker.upper()
        await self._session.execute(
            delete(TickerLiveOptionOpportunityModel).where(
                TickerLiveOptionOpportunityModel.ticker == ticker_upper,
                TickerLiveOptionOpportunityModel.side == side,
            )
        )
        if not opportunities:
            return

        now = datetime.now(UTC)
        rows = [
            _live_opp_row_payload(opp, fallback_updated_at=now)
            for opp in opportunities
        ]
        await self._session.execute(
            insert(TickerLiveOptionOpportunityModel),
            rows,
        )

    async def append_history(
        self,
        opportunities: list[LiveOpportunity],
    ) -> None:
        """Append every supplied row to ``ticker_option_opportunity_history``.

        This table is the append-only archive — never updated, never
        deleted. Called once per recalc cycle with the full CALL+PUT batch.
        """
        if not opportunities:
            return
        now = datetime.now(UTC)
        rows = [
            _history_row_payload(opp, fallback_updated_at=now)
            for opp in opportunities
        ]
        await self._session.execute(
            insert(TickerOptionOpportunityHistoryModel),
            rows,
        )

    async def commit(self) -> None:
        await self._session.commit()

    async def mark_disconnected(self, tickers: Iterable[str]) -> None:
        """Stamp every known row as disconnected (for graceful shutdown)."""
        for ticker in tickers:
            row = await self._session.scalar(
                select(TickerMarketDataModel).where(
                    TickerMarketDataModel.ticker == ticker.upper()
                )
            )
            if row is not None:
                row.feed_status = "disconnected"
                row.updated_at = datetime.now(UTC)
        await self._session.commit()

    # ------------------------------------------------------------------ reads
    async def get_quote(self, ticker: str, *, stale_threshold_s: int) -> LiveQuote | None:
        row = await self._session.scalar(
            select(TickerMarketDataModel).where(
                TickerMarketDataModel.ticker == ticker.upper()
            )
        )
        if row is None:
            return None
        return self._quote_from_row(row, stale_threshold_s=stale_threshold_s)

    async def get_opportunities(
        self,
        ticker: str,
        *,
        stale_threshold_s: int,
        limit: int | None = None,
        offset: int = 0,
        side: SideLiteral | None = None,
        sort: str = "ranking_score",
        order: str = "desc",
    ) -> LiveOpportunityBundle | None:
        stmt = select(TickerLiveOptionOpportunityModel).where(
            TickerLiveOptionOpportunityModel.ticker == ticker.upper()
        )
        if side is not None:
            stmt = stmt.where(TickerLiveOptionOpportunityModel.side == side)

        sort_col = _resolve_sort_column(sort)
        if order.lower() == "asc":
            stmt = stmt.order_by(sort_col.asc().nullslast())
        else:
            stmt = stmt.order_by(sort_col.desc().nullslast())

        if offset > 0:
            stmt = stmt.offset(int(offset))
        if limit is not None and limit > 0:
            stmt = stmt.limit(int(limit))

        rows = (await self._session.execute(stmt)).scalars().all()
        if not rows:
            return None
        return self._bundle_from_rows(list(rows), stale_threshold_s=stale_threshold_s)

    async def count_opportunities(
        self,
        ticker: str,
        *,
        side: SideLiteral | None = None,
    ) -> int:
        stmt = select(func.count(TickerLiveOptionOpportunityModel.id)).where(
            TickerLiveOptionOpportunityModel.ticker == ticker.upper()
        )
        if side is not None:
            stmt = stmt.where(TickerLiveOptionOpportunityModel.side == side)
        value = (await self._session.execute(stmt)).scalar()
        return int(value or 0)

    async def get_opportunity_history(
        self,
        ticker: str,
        *,
        snapshot_date: str | None = None,
        since: datetime | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> tuple[list[OpportunityHistoryEntry], int]:
        """Return rows from ``ticker_option_opportunity_history`` + total."""
        base = select(TickerOptionOpportunityHistoryModel).where(
            TickerOptionOpportunityHistoryModel.ticker == ticker.upper()
        )
        if snapshot_date is not None:
            base = base.where(
                TickerOptionOpportunityHistoryModel.snapshot_date == snapshot_date
            )
        if since is not None:
            base = base.where(
                TickerOptionOpportunityHistoryModel.generated_at >= since
            )

        count_stmt = select(func.count()).select_from(base.subquery())
        total = int((await self._session.execute(count_stmt)).scalar() or 0)

        stmt = (
            base.order_by(
                desc(TickerOptionOpportunityHistoryModel.generated_at),
                desc(TickerOptionOpportunityHistoryModel.ranking_score),
            )
            .offset(int(max(0, offset)))
            .limit(int(max(1, limit)))
        )
        rows = (await self._session.execute(stmt)).scalars().all()

        out = [self._history_entry_from_row(row) for row in rows]
        return out, total

    async def get_dashboard_live_bundle(
        self,
        tickers: Iterable[str],
        *,
        stale_threshold_s: int,
        connection_status: FeedStatus,
    ) -> DashboardLiveBundle:
        """Single-pass read of every live row for the dashboard grid.

        Two queries (one per table) plus an in-memory fan-out, so the
        whole bulk endpoint stays cheap even when every ticker has
        hundreds of rows persisted.
        """
        ticker_set = {t.upper() for t in tickers}

        quote_rows = (
            await self._session.execute(
                select(TickerMarketDataModel).where(
                    TickerMarketDataModel.ticker.in_(ticker_set)
                )
            )
        ).scalars().all()
        opp_rows = (
            await self._session.execute(
                select(TickerLiveOptionOpportunityModel)
                .where(
                    TickerLiveOptionOpportunityModel.ticker.in_(ticker_set)
                )
                .order_by(
                    TickerLiveOptionOpportunityModel.ticker,
                    TickerLiveOptionOpportunityModel.side,
                    desc(TickerLiveOptionOpportunityModel.ranking_score),
                )
            )
        ).scalars().all()

        quotes_by_ticker = {row.ticker: row for row in quote_rows}
        opps_by_ticker: dict[str, list[TickerLiveOptionOpportunityModel]] = {}
        for row in opp_rows:
            opps_by_ticker.setdefault(row.ticker, []).append(row)

        prices_updated_at: datetime | None = None
        opportunities_updated_at: datetime | None = None
        for row in quote_rows:
            if row.updated_at is not None:
                if prices_updated_at is None or row.updated_at > prices_updated_at:
                    prices_updated_at = row.updated_at
        for row in opp_rows:
            if row.updated_at is not None:
                if (
                    opportunities_updated_at is None
                    or row.updated_at > opportunities_updated_at
                ):
                    opportunities_updated_at = row.updated_at

        entries: dict[str, DashboardLiveTickerEntry] = {}
        for ticker in ticker_set:
            quote_row = quotes_by_ticker.get(ticker)
            opp_for_ticker = opps_by_ticker.get(ticker, [])
            entries[ticker] = DashboardLiveTickerEntry(
                ticker=ticker,
                quote=(
                    self._quote_from_row(quote_row, stale_threshold_s=stale_threshold_s)
                    if quote_row is not None
                    else None
                ),
                opportunities=(
                    self._bundle_from_rows(
                        opp_for_ticker, stale_threshold_s=stale_threshold_s
                    )
                    if opp_for_ticker
                    else None
                ),
            )

        return DashboardLiveBundle(
            feed_status=connection_status,
            prices_updated_at=prices_updated_at,
            opportunities_updated_at=opportunities_updated_at,
            tickers=entries,
        )

    async def get_candles_1m(
        self,
        ticker: str,
        *,
        since: datetime,
        until: datetime | None = None,
        limit: int = 120,
    ) -> list:
        """Return 1-minute OHLCV candles for ``ticker`` in ascending ts order."""
        from app.db.models.tables import MarketCandle1mModel
        from app.services.market_data.candle_aggregator import Candle1m

        stmt = select(MarketCandle1mModel).where(
            MarketCandle1mModel.ticker == ticker.upper(),
            MarketCandle1mModel.ts >= since,
        )
        if until is not None:
            stmt = stmt.where(MarketCandle1mModel.ts <= until)
        stmt = stmt.order_by(MarketCandle1mModel.ts.asc()).limit(max(1, limit))

        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            Candle1m(
                ticker=row.ticker,
                ts=row.ts,
                open=float(row.open) if row.open is not None else 0.0,
                high=float(row.high) if row.high is not None else 0.0,
                low=float(row.low) if row.low is not None else 0.0,
                close=float(row.close) if row.close is not None else 0.0,
                volume=int(row.volume) if row.volume is not None else 0,
            )
            for row in rows
        ]

    async def get_opportunity_versions(
        self,
        tickers: Iterable[str],
    ) -> dict[str, dict[str, UUID | None]]:
        """Return the latest opportunity_version per (ticker, side).

        Used by the WebSocket fanout and the bulk live endpoint so clients
        can detect drift even if they miss a push message.
        """
        ticker_set = {t.upper() for t in tickers}
        if not ticker_set:
            return {}

        stmt = (
            select(
                TickerLiveOptionOpportunityModel.ticker,
                TickerLiveOptionOpportunityModel.side,
                func.max(TickerLiveOptionOpportunityModel.opportunity_version),
            )
            .where(TickerLiveOptionOpportunityModel.ticker.in_(ticker_set))
            .group_by(
                TickerLiveOptionOpportunityModel.ticker,
                TickerLiveOptionOpportunityModel.side,
            )
        )
        out: dict[str, dict[str, UUID | None]] = {}
        for ticker, side, version in (await self._session.execute(stmt)).all():
            out.setdefault(ticker, {})[side] = version
        return out

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _quote_from_row(
        row: TickerMarketDataModel,
        *,
        stale_threshold_s: int,
    ) -> LiveQuote:
        bucket = _bucket_feed_status(row.updated_at, stale_threshold_s)
        if row.feed_status in {"disconnected"}:
            status: FeedStatus = "disconnected"
        elif bucket in {"disconnected", "stale"}:
            status = bucket
        else:
            status = row.feed_status if row.feed_status in {"live", "stale"} else "live"

        return LiveQuote(
            ticker=row.ticker,
            last_price=_to_float(row.last_price),
            bid=_to_float(row.bid),
            ask=_to_float(row.ask),
            change_abs=_to_float(row.change_abs),
            change_pct=_to_float(row.change_pct),
            volume=row.volume,
            prev_close=_to_float(row.prev_close),
            feed_status=status,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _bundle_from_rows(
        rows: list[TickerLiveOptionOpportunityModel],
        *,
        stale_threshold_s: int,
    ) -> LiveOpportunityBundle:
        calls: list[LiveOpportunity] = []
        puts: list[LiveOpportunity] = []
        most_recent: datetime | None = None
        call_version: UUID | None = None
        put_version: UUID | None = None
        for row in rows:
            if row.updated_at is not None:
                if most_recent is None or row.updated_at > most_recent:
                    most_recent = row.updated_at
            entry = _row_to_live_opp(row)
            if row.side == "call":
                calls.append(entry)
                if row.opportunity_version is not None and call_version is None:
                    call_version = row.opportunity_version
            elif row.side == "put":
                puts.append(entry)
                if row.opportunity_version is not None and put_version is None:
                    put_version = row.opportunity_version

        feed_status = _bucket_feed_status(most_recent, stale_threshold_s)
        calls.sort(key=lambda r: -(r.ranking_score or 0))
        puts.sort(key=lambda r: -(r.ranking_score or 0))
        return LiveOpportunityBundle(
            calls=calls,
            puts=puts,
            call_version=call_version,
            put_version=put_version,
            updated_at=most_recent,
            feed_status=feed_status,
        )

    @staticmethod
    def _history_entry_from_row(
        row: TickerOptionOpportunityHistoryModel,
    ) -> OpportunityHistoryEntry:
        return OpportunityHistoryEntry(
            id=row.id,
            ticker=row.ticker,
            side=row.side,  # type: ignore[arg-type]
            combo=row.combo,
            strike_long_wing_a=float(row.strike_long_wing_a),
            strike_short_body=float(row.strike_short_body),
            strike_long_wing_b=float(row.strike_long_wing_b),
            expiration=row.expiration,
            expiry_days=int(row.expiry_days),
            delta_pct=_to_float(row.delta_pct),
            premium=_to_float(row.premium) or 0.0,
            init_margin=_to_float(row.init_margin),
            maint_margin=_to_float(row.maint_margin),
            init_margin_source=(row.init_margin_source or "deterministic"),  # type: ignore[arg-type]
            liquidity=int(row.liquidity or 0),
            minimum_open_interest=row.minimum_open_interest,
            minimum_volume=row.minimum_volume,
            oi_leg1=row.oi_leg1,
            oi_leg2=row.oi_leg2,
            oi_leg3=row.oi_leg3,
            vol_leg1=row.vol_leg1,
            vol_leg2=row.vol_leg2,
            vol_leg3=row.vol_leg3,
            iv_leg1=_to_float(row.iv_leg1),
            iv_leg2=_to_float(row.iv_leg2),
            iv_leg3=_to_float(row.iv_leg3),
            mid_leg1=_to_float(row.mid_leg1),
            mid_leg2=_to_float(row.mid_leg2),
            mid_leg3=_to_float(row.mid_leg3),
            credit_efficiency=_to_float(row.credit_efficiency),
            ranking_score=_to_float(row.ranking_score),
            underlying_price=_to_float(row.underlying_price),
            iv=_to_float(row.iv),
            opportunity_version=row.opportunity_version,
            generated_at=row.generated_at,
            snapshot_date=row.snapshot_date.isoformat()
            if row.snapshot_date is not None
            else "",
        )


_SORT_COLUMN_MAP = {
    "ranking_score": TickerLiveOptionOpportunityModel.ranking_score,
    "score": TickerLiveOptionOpportunityModel.ranking_score,
    "credit_efficiency": TickerLiveOptionOpportunityModel.credit_efficiency,
    "premium": TickerLiveOptionOpportunityModel.premium,
    "margin": TickerLiveOptionOpportunityModel.init_margin,
    "liquidity": TickerLiveOptionOpportunityModel.liquidity,
    "delta": TickerLiveOptionOpportunityModel.delta_pct,
    "delta_pct": TickerLiveOptionOpportunityModel.delta_pct,
    "expiry_days": TickerLiveOptionOpportunityModel.expiry_days,
    "rank": TickerLiveOptionOpportunityModel.rank,
}


def _resolve_sort_column(sort: str):
    return _SORT_COLUMN_MAP.get(sort.lower(), TickerLiveOptionOpportunityModel.ranking_score)
