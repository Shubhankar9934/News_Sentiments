"""High-level IBKR client used by the live worker and opportunity service.

This is the only module that imports ``ib_async`` at the boundary
(except ``IbkrConnection`` for connection lifecycle). Everything else in
the package consumes the typed dataclasses defined here so the IBKR types
never leak into the rest of the codebase.

Four operations:

    1. ``subscribe_quotes(symbols)``    — start streaming live ticks for
                                          all 12 watchlist underlyings.
                                          Idempotent; called once at
                                          worker startup.
    2. ``drain_quotes()``               — pull every quote that has updated
                                          since the last drain. Returns
                                          typed ``LiveQuote`` instances
                                          ready for the repository.
    3. ``snapshot_option_quotes(...)``  — request a one-shot snapshot of
                                          a list of option contracts and
                                          return their bid/ask/oi/vol.
    4. ``what_if_margin(combo_legs)``   — build a 3-leg BAG order with
                                          ``whatIf=True`` and return the
                                          (init, maint) margin pair.

When IBKR is disconnected every method short-circuits and returns ``None``
or empty results — callers must handle this gracefully.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Iterable

import structlog

from app.core.config import Settings
from app.services.market_data.ibkr_connection import IbkrConnection
from app.services.market_data.schemas import LiveQuote

if TYPE_CHECKING:  # pragma: no cover
    from ib_async import Contract, Option

log = structlog.get_logger(__name__)


# --------------------------------------------------------------------------
# Helper dataclasses (intentionally not pydantic — these are internal)
# --------------------------------------------------------------------------
@dataclass
class OptionContractInfo:
    """Lightweight handle on an IBKR option contract.

    Holds enough to (a) request a snapshot quote, (b) build a BAG leg, and
    (c) compute liquidity / display labels — without leaking the raw
    ``ib_async.Option`` to other modules.
    """

    symbol: str
    strike: float
    right: str  # "C" | "P"
    expiry: str  # YYYYMMDD
    exchange: str = "SMART"
    multiplier: str = "100"
    con_id: int | None = None  # populated after qualification

    def with_con_id(self, con_id: int) -> "OptionContractInfo":
        return OptionContractInfo(
            symbol=self.symbol,
            strike=self.strike,
            right=self.right,
            expiry=self.expiry,
            exchange=self.exchange,
            multiplier=self.multiplier,
            con_id=con_id,
        )


@dataclass
class OptionQuote:
    """Snapshot quote for one option contract."""

    con_id: int | None
    bid: float | None
    ask: float | None
    last: float | None
    open_interest: int | None
    volume: int | None
    implied_vol: float | None = None

    @property
    def mid(self) -> float | None:
        if self.bid is None or self.ask is None:
            return self.last
        if self.bid <= 0 or self.ask <= 0:
            return self.last
        return round((self.bid + self.ask) / 2.0, 4)

    @property
    def spread_pct(self) -> float | None:
        m = self.mid
        if m is None or m <= 0 or self.bid is None or self.ask is None:
            return None
        return round((self.ask - self.bid) / m * 100.0, 4)


@dataclass
class ComboLeg:
    """A single leg of a Reverse-BWB BAG order.

    ``ratio`` is the absolute number of contracts (always >=1); ``action``
    is BUY for long legs and SELL for short legs. The combined order is
    submitted to IBKR with these legs and ``whatIf=True``.
    """

    con_id: int
    ratio: int
    action: str  # "BUY" | "SELL"
    exchange: str = "SMART"


@dataclass
class WhatIfResult:
    init_margin: float | None
    maint_margin: float | None


@dataclass
class _StreamSlot:
    """In-memory state for one streaming underlying."""

    ticker_obj: object | None = None  # ``ib_async.Ticker``
    last_seen_at: datetime | None = None
    dirty: bool = False
    prev_close: float | None = None


@dataclass
class _SubscriptionState:
    slots: dict[str, _StreamSlot] = field(default_factory=dict)
    started: bool = False


# --------------------------------------------------------------------------
# Service
# --------------------------------------------------------------------------
class MarketDataService:
    """High-level IBKR operations for the live dashboard.

    Stateless across requests — except for ``self._subs`` which holds the
    streaming-underlying state. Constructed once and reused.
    """

    def __init__(self, settings: Settings, connection: IbkrConnection) -> None:
        self._settings = settings
        self._connection = connection
        self._subs = _SubscriptionState()
        self._stream_lock = asyncio.Lock()
        self._req_id_lock = threading.Lock()

    # --------------------------------------------------------------- streaming
    async def subscribe_quotes(self, symbols: Iterable[str]) -> bool:
        """Subscribe each symbol to a streaming Stock market data feed.

        Idempotent — calling twice with the same symbols is a no-op. The
        underlying ``ib_async.Ticker`` updates in-place on every tick;
        ``drain_quotes()`` reads the latest snapshot and clears the dirty
        flag.
        """
        ib = self._connection.ib
        if ib is None:
            log.info("market_data.subscribe_quotes.skip", reason="not_connected")
            return False

        from ib_async import Stock

        async with self._stream_lock:
            symbol_list = sorted({s.upper() for s in symbols})
            for sym in symbol_list:
                if sym in self._subs.slots and self._subs.slots[sym].ticker_obj is not None:
                    continue
                contract = Stock(sym, "SMART", "USD")
                try:
                    await ib.qualifyContractsAsync(contract)
                except Exception as exc:
                    log.warning("market_data.qualify_failed", ticker=sym, error=str(exc))
                    continue
                ticker_obj = ib.reqMktData(
                    contract,
                    genericTickList="",
                    snapshot=False,
                    regulatorySnapshot=False,
                )
                slot = self._subs.slots.setdefault(sym, _StreamSlot())
                slot.ticker_obj = ticker_obj
                # ib_async raises ``updateEvent`` when any tick lands
                ticker_obj.updateEvent += self._make_tick_handler(sym)
                log.info("market_data.subscribed", ticker=sym)
            self._subs.started = True
        return True

    def _make_tick_handler(self, sym: str):
        slots = self._subs.slots

        def _handler(_ticker: object) -> None:
            slot = slots.get(sym)
            if slot is None:
                return
            slot.last_seen_at = datetime.now(UTC)
            slot.dirty = True

        return _handler

    async def drain_quotes(self) -> list[LiveQuote]:
        """Return a snapshot of every dirty subscription and clear the flag."""
        if self._connection.ib is None:
            return []
        out: list[LiveQuote] = []
        async with self._stream_lock:
            for sym, slot in self._subs.slots.items():
                ticker_obj = slot.ticker_obj
                if ticker_obj is None:
                    continue
                if not slot.dirty:
                    continue
                slot.dirty = False
                quote = self._ticker_to_quote(sym, ticker_obj, slot)
                if quote is not None:
                    out.append(quote)
        return out

    def _ticker_to_quote(
        self,
        sym: str,
        ticker_obj: object,
        slot: _StreamSlot,
    ) -> LiveQuote | None:
        last = self._safe_float(getattr(ticker_obj, "last", None))
        if last is None:
            last = self._safe_float(getattr(ticker_obj, "marketPrice", lambda: None)())
        if last is None:
            close = self._safe_float(getattr(ticker_obj, "close", None))
            if close is not None:
                last = close

        bid = self._safe_float(getattr(ticker_obj, "bid", None))
        ask = self._safe_float(getattr(ticker_obj, "ask", None))
        prev_close = self._safe_float(getattr(ticker_obj, "close", None))
        if prev_close is not None:
            slot.prev_close = prev_close
        else:
            prev_close = slot.prev_close

        volume = self._safe_int(getattr(ticker_obj, "volume", None))

        change_abs: float | None = None
        change_pct: float | None = None
        if last is not None and prev_close is not None and prev_close > 0:
            change_abs = round(last - prev_close, 4)
            change_pct = round((last - prev_close) / prev_close * 100.0, 4)

        return LiveQuote(
            ticker=sym,
            last_price=last,
            bid=bid,
            ask=ask,
            change_abs=change_abs,
            change_pct=change_pct,
            volume=volume,
            prev_close=prev_close,
            feed_status="live",
            updated_at=slot.last_seen_at or datetime.now(UTC),
        )

    @staticmethod
    def _safe_float(value: object) -> float | None:
        try:
            f = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        # IBKR uses NaN/-1 for "no data" on many fields.
        if f != f:  # NaN
            return None
        if f < 0:
            return None
        return f

    @staticmethod
    def _safe_int(value: object) -> int | None:
        try:
            i = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        if i < 0:
            return None
        return i

    async def cancel_subscriptions(self) -> None:
        ib = self._connection.ib
        if ib is None:
            return
        async with self._stream_lock:
            for sym, slot in self._subs.slots.items():
                ticker_obj = slot.ticker_obj
                if ticker_obj is None:
                    continue
                contract = getattr(ticker_obj, "contract", None)
                if contract is not None:
                    try:
                        ib.cancelMktData(contract)
                    except Exception as exc:  # pragma: no cover - defensive
                        log.warning(
                            "market_data.cancel_failed",
                            ticker=sym,
                            error=str(exc),
                        )
                slot.ticker_obj = None
            self._subs.slots.clear()
            self._subs.started = False

    # ------------------------------------------------------------ option chain
    async def snapshot_chain(
        self,
        ticker: str,
        *,
        dte_min: int,
        dte_max: int,
    ) -> tuple[list[str], list[float]] | None:
        """Return ``(expirations, strikes)`` for the SMART chain.

        Filters expirations by DTE range. Returns ``None`` when IBKR is
        offline or returns an empty result.
        """
        ib = self._connection.ib
        if ib is None:
            return None

        from ib_async import Stock

        try:
            stock = Stock(ticker.upper(), "SMART", "USD")
            await ib.qualifyContractsAsync(stock)
            chains = await ib.reqSecDefOptParamsAsync(
                stock.symbol,
                "",
                stock.secType,
                stock.conId,
            )
        except Exception as exc:
            log.warning("market_data.snapshot_chain.failed", ticker=ticker, error=str(exc))
            return None

        smart = next((c for c in chains if c.exchange == "SMART"), None)
        if smart is None:
            return None

        expirations = self._filter_expirations(
            smart.expirations,
            dte_min=dte_min,
            dte_max=dte_max,
        )
        strikes = sorted(float(s) for s in smart.strikes)
        return expirations, strikes

    @staticmethod
    def _filter_expirations(
        expirations: Iterable[str],
        *,
        dte_min: int,
        dte_max: int,
    ) -> list[str]:
        today = datetime.now(UTC).date()
        out: list[tuple[int, str]] = []
        for raw in expirations:
            try:
                exp_date = datetime.strptime(raw, "%Y%m%d").date()
            except ValueError:
                continue
            dte = (exp_date - today).days
            if dte_min <= dte <= dte_max:
                out.append((dte, raw))
        out.sort()
        return [exp for _dte, exp in out]

    async def snapshot_option_quotes(
        self,
        contracts: list[OptionContractInfo],
    ) -> dict[str, OptionQuote]:
        """One-shot snapshot of a list of option contracts.

        Keyed by ``con_id`` (or by ``"strike-right"`` if con_id missing).
        Empty dict when disconnected.
        """
        ib = self._connection.ib
        if ib is None or not contracts:
            return {}

        from ib_async import Option

        ib_contracts: list[Option] = []
        original_keys: list[str] = []
        for info in contracts:
            opt = Option(
                info.symbol,
                info.expiry,
                info.strike,
                info.right,
                info.exchange,
                multiplier=info.multiplier,
                currency="USD",
            )
            ib_contracts.append(opt)
            original_keys.append(self._opt_key(info))

        try:
            qualified = await ib.qualifyContractsAsync(*ib_contracts)
        except Exception as exc:
            log.warning("market_data.qualify_options_failed", error=str(exc))
            return {}

        # Use snapshot=True for one-shot pricing — this respects IBKR's
        # snapshot pacing limits (~50 simultaneous) but doesn't burn a
        # streaming subscription per leg.
        tickers = []
        for contract in qualified:
            if contract is None or contract.conId == 0:
                tickers.append(None)
                continue
            tickers.append(
                ib.reqMktData(
                    contract,
                    genericTickList="",  # generic ticks are not available in snapshot mode
                    snapshot=True,
                    regulatorySnapshot=False,
                )
            )

        # Snapshot tickers fire ``snapshotEnd`` after IBKR delivers the data.
        # Scale the wait proportionally: IBKR handles roughly 25 snapshots/s.
        # Add a 3-second buffer for network round-trip and IBKR processing.
        n_requested = sum(1 for t in tickers if t is not None)
        wait_s = max(3.0, (n_requested / 25.0) + 3.0)
        try:
            await ib.sleepAsync(wait_s)
        except Exception:
            await asyncio.sleep(wait_s)

        out: dict[str, OptionQuote] = {}
        for key, contract, ticker_obj in zip(original_keys, qualified, tickers):
            if ticker_obj is None or contract is None:
                continue
            con_id = int(getattr(contract, "conId", 0)) or None
            quote = OptionQuote(
                con_id=con_id,
                bid=self._safe_float(getattr(ticker_obj, "bid", None)),
                ask=self._safe_float(getattr(ticker_obj, "ask", None)),
                last=self._safe_float(getattr(ticker_obj, "last", None)),
                open_interest=self._extract_open_interest(ticker_obj),
                volume=self._safe_int(getattr(ticker_obj, "volume", None)),
                implied_vol=self._safe_float(
                    getattr(getattr(ticker_obj, "modelGreeks", None), "impliedVol", None)
                )
                if getattr(ticker_obj, "modelGreeks", None) is not None
                else None,
            )
            out[key] = quote

        valid_mids = sum(1 for q in out.values() if q.mid is not None)
        log.info(
            "market_data.snapshot_quotes_result",
            total_requested=len(contracts),
            qualified=n_requested,
            returned=len(out),
            valid_mid=valid_mids,
            wait_s=round(wait_s, 1),
        )
        return out

    @staticmethod
    def _extract_open_interest(ticker_obj: object) -> int | None:
        for attr in ("callOpenInterest", "putOpenInterest"):
            val = getattr(ticker_obj, attr, None)
            if val is not None:
                try:
                    n = int(val)
                except (TypeError, ValueError):
                    continue
                if n > 0:
                    return n
        return None

    @staticmethod
    def _opt_key(info: OptionContractInfo) -> str:
        return f"{info.symbol}|{info.expiry}|{info.strike}|{info.right}"

    @staticmethod
    def opt_key(info: OptionContractInfo) -> str:
        """Public version of ``_opt_key`` for callers that need to look up
        snapshot results."""
        return MarketDataService._opt_key(info)

    # -------------------------------------------------------------- what-if
    async def what_if_margin(self, legs: list[ComboLeg]) -> WhatIfResult | None:
        """Submit a BAG order with ``whatIf=True`` and parse the margin.

        Returns ``None`` when disconnected, when the order is rejected, or
        when IBKR doesn't return margin (e.g. paper account without
        permissions). Callers must handle ``None`` and fall back to the
        formula-based ``2 * wing_width * 100`` placeholder.
        """
        ib = self._connection.ib
        if ib is None or not legs:
            return None

        from ib_async import Bag, ComboLeg as IbComboLeg, Order

        symbol = "BAG-WHAT-IF"
        bag = Bag(symbol=symbol, currency="USD", exchange="SMART")
        ib_legs: list[IbComboLeg] = []
        for leg in legs:
            ib_leg = IbComboLeg(
                conId=leg.con_id,
                ratio=int(leg.ratio),
                action=leg.action,
                exchange=leg.exchange,
            )
            ib_legs.append(ib_leg)
        bag.comboLegs = ib_legs

        order = Order()
        order.action = "BUY"  # convention; whatIf doesn't actually fill
        order.orderType = "MKT"
        order.totalQuantity = 1
        order.whatIf = True

        try:
            state = await ib.whatIfOrderAsync(bag, order)
        except Exception as exc:
            log.warning("market_data.what_if.failed", error=str(exc))
            return None

        return WhatIfResult(
            init_margin=self._parse_margin(getattr(state, "initMarginChange", None)),
            maint_margin=self._parse_margin(getattr(state, "maintMarginChange", None)),
        )

    @staticmethod
    def _parse_margin(raw: object) -> float | None:
        if raw is None:
            return None
        try:
            value = float(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        # IBKR returns '1.7976931348623157e+308' (DBL_MAX) when the margin
        # change isn't applicable; treat that as "unknown".
        if value > 1e10 or value < -1e10:
            return None
        return abs(value)
