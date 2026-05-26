"""Numeric liquidity scoring for Reverse BWB opportunities.

The dashboard requirement is unambiguous: liquidity is **numeric** — never
``Good`` / ``Average`` / ``Excellent`` / ``Poor``. The Workstation uses
the minimum open interest across the three leg strikes as the headline
liquidity scalar (a 0-OI leg means the entire combo is illiquid).

This module also exposes helpers for the per-leg OI / volume aggregates
that drive the per-leg explorer columns and the ranking-engine logarithm.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.market_data.combo_geometry import numeric_liquidity


@dataclass(frozen=True)
class LiquidityProfile:
    """Aggregated liquidity profile for a Reverse BWB combo."""

    liquidity: int  # headline = min(OI per leg)
    minimum_open_interest: int  # alias for clarity in the schema
    minimum_volume: int
    oi_legs: tuple[int | None, int | None, int | None]
    vol_legs: tuple[int | None, int | None, int | None]


def compute_liquidity_profile(
    *,
    oi_legs: tuple[int | None, int | None, int | None],
    vol_legs: tuple[int | None, int | None, int | None],
) -> LiquidityProfile:
    """Build the per-combo liquidity profile from raw per-leg quotes."""

    oi1, oi2, oi3 = oi_legs
    liquidity = numeric_liquidity(oi_leg1=oi1, oi_leg2=oi2, oi_leg3=oi3)

    vol_values = [v for v in vol_legs if v is not None]
    min_vol = min(vol_values) if vol_values else 0

    return LiquidityProfile(
        liquidity=liquidity,
        minimum_open_interest=liquidity,
        minimum_volume=int(max(0, min_vol)),
        oi_legs=oi_legs,
        vol_legs=vol_legs,
    )


def meets_liquidity_floor(
    profile: LiquidityProfile,
    *,
    min_leg_oi: int,
) -> bool:
    """Whether each leg meets the configured minimum OI.

    A single illiquid leg kills the whole combo — the trader will get
    skipped fills or pay a wide spread otherwise.
    """
    if min_leg_oi <= 0:
        return True
    for oi in profile.oi_legs:
        # None means OI data was unavailable from IBKR (snapshot mode does not
        # return generic ticks like option OI). Treat as "unknown" — do not
        # reject based on missing data; only reject when OI is known and low.
        if oi is not None and oi < min_leg_oi:
            return False
    return True
