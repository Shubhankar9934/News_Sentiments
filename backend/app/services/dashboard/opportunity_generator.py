"""Placeholder Reverse-BWB option opportunity generator.

V1: deterministic strikes synthesised from the existing
``options_intelligence`` block. No live chain access, no IO.

V2: an ``IbkrOpportunitySource`` implementation will satisfy the same
``OpportunitySource`` protocol and slot in via the
``WatchlistBatchService`` constructor without any route changes.

Combo notation follows the Reverse Broken-Wing Butterfly convention
``short_inner / long_short / long_outer`` (3 strikes per side).
"""

from __future__ import annotations

import math
from typing import Any, Protocol

import structlog

from app.services.dashboard.schemas import (
    LiquidityLabel,
    OptionOpportunities,
    OptionOpportunity,
)
from app.services.dashboard.watchlist import WATCHLIST_TIER_KEY_BY_SYMBOL

log = structlog.get_logger(__name__)


class OpportunitySource(Protocol):
    """Pluggable interface so the IBKR swap is a single new class.

    Implementations MUST return at least an empty
    ``OptionOpportunities(calls=[], puts=[])`` instance — never raise.
    """

    def generate(self, ticker: str, report: dict[str, Any]) -> OptionOpportunities:
        ...


def _liquidity_for_ticker(ticker: str) -> LiquidityLabel:
    """Crude liquidity proxy until IBKR provides real bid/ask widths.

    Index ETFs and mega-caps are Good, everything else is Average. The
    vocabulary follows the narrowed ``LiquidityLabel`` Literal
    (``Poor`` / ``Average`` / ``Good``).
    """

    tier = WATCHLIST_TIER_KEY_BY_SYMBOL.get(ticker.upper())
    if tier in ("tier-1", "tier-2"):
        return "Good"
    return "Average"


def _round_strike(price: float, step: float) -> float:
    """Snap to a half/full dollar strike that the wing actually trades at."""

    if step <= 0:
        step = 0.5
    return round(price / step) * step


def _strike_step(price: float) -> float:
    if price >= 500:
        return 5.0
    if price >= 100:
        return 1.0
    if price >= 25:
        return 0.5
    return 0.5


def _expiry_label(dte: int) -> str:
    if dte <= 1:
        return "0D"
    return f"{int(dte)}D"


def _format_combo(short_inner: float, long_short: float, long_outer: float) -> str:
    def _fmt(v: float) -> str:
        if abs(v - round(v)) < 1e-6:
            return f"{int(round(v))}"
        return f"{v:.1f}"

    return f"{_fmt(short_inner)}/{_fmt(long_short)}/{_fmt(long_outer)}"


def _build_side(
    *,
    side: str,
    last_close: float,
    sigma_dollars: float,
    step: float,
    dte_short: int,
    dte_long: int,
    liquidity: LiquidityLabel,
) -> list[OptionOpportunity]:
    """Two combos per side, spaced at ~0.5 sigma and ~1.0 sigma offset.

    All numbers are deterministic placeholders calibrated so the dashboard
    surfaces sensible relative values; they will be replaced wholesale
    when IBKR comes online.
    """

    sign = 1 if side == "CALL" else -1
    rows: list[OptionOpportunity] = []

    for idx, offset_sigma in enumerate((0.5, 1.0)):
        anchor = last_close + sign * offset_sigma * sigma_dollars
        short_inner = _round_strike(anchor, step)
        wing_width = max(step, _round_strike(0.5 * sigma_dollars, step))
        long_short = short_inner + sign * wing_width
        long_outer = long_short + sign * 2 * wing_width

        # Premium: ~0.4-0.6% of price, narrowing the further OTM we go.
        premium_pct = 0.006 - 0.0015 * idx
        premium = round(max(0.05 * last_close * 0.01, last_close * premium_pct), 2)

        # Margin ~ wing width * 100 (1 standard contract), padded for spread.
        margin = round(wing_width * 100 * 1.05, 0)

        expiry = _expiry_label(dte_short if idx == 0 else dte_long)

        rows.append(
            OptionOpportunity(
                combo=_format_combo(short_inner, long_short, long_outer),
                expiry=expiry,
                premium=premium,
                margin=margin,
                liquidity=liquidity,
            )
        )

    return rows


class PlaceholderOpportunitySource:
    """V1 implementation — no IO, deterministic from existing report data."""

    def generate(self, ticker: str, report: dict[str, Any]) -> OptionOpportunities:
        options = report.get("options_intelligence") or {}
        if not options:
            log.info("opportunities.skip", ticker=ticker, reason="no_options_intelligence")
            return OptionOpportunities()

        last_close = options.get("last_close")
        expected_range = options.get("expected_range") or {}
        horizon = options.get("horizon_days") or 3

        if not last_close or last_close <= 0:
            return OptionOpportunities()

        low = expected_range.get("low")
        high = expected_range.get("high")
        if isinstance(low, (int, float)) and isinstance(high, (int, float)):
            sigma_dollars = max((high - low) / 2.0, 0.5)
        else:
            sigma_pct = expected_range.get("sigma_pct") or 1.5
            sigma_dollars = max(last_close * float(sigma_pct) / 100.0, 0.5)

        # Avoid pathological sigmas swamping strike spacing on tiny prices.
        sigma_dollars = min(sigma_dollars, last_close * 0.15)

        step = _strike_step(float(last_close))
        liquidity = _liquidity_for_ticker(ticker)

        # Short-dated combo + slightly longer-dated combo so the trader sees
        # both a 2D and a 5D option when DTE is small.
        dte_short = max(1, int(round(horizon))) if horizon else 2
        dte_long = max(dte_short + 3, int(math.ceil(dte_short * 2.5)))

        calls = _build_side(
            side="CALL",
            last_close=float(last_close),
            sigma_dollars=float(sigma_dollars),
            step=step,
            dte_short=dte_short,
            dte_long=dte_long,
            liquidity=liquidity,
        )
        puts = _build_side(
            side="PUT",
            last_close=float(last_close),
            sigma_dollars=float(sigma_dollars),
            step=step,
            dte_short=dte_short,
            dte_long=dte_long,
            liquidity=liquidity,
        )

        return OptionOpportunities(calls=calls, puts=puts)


def default_opportunity_source() -> OpportunitySource:
    """Factory for the current default source (V1: placeholder)."""

    return PlaceholderOpportunitySource()
