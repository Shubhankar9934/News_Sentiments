"""Numeric liquidity scoring for Reverse BWB opportunities.

Liquidity = MIN( BidSize_leg / abs(Ratio_leg) ) across all strategy legs.

For a standard 3-leg Put/Call Butterfly (ratios +1 / -2 / +1):

    Capacity_leg1 = BidSize_leg1 / 1
    Capacity_leg2 = BidSize_leg2 / 2   ← short body doubled
    Capacity_leg3 = BidSize_leg3 / 1

    Liquidity = MIN(Capacity_leg1, Capacity_leg2, Capacity_leg3)

BidSize (IBKR TickType 0) represents the number of contracts actually
available at the current bid — i.e. immediately executable depth.

The formula is strategy-independent: pass any ``ratios`` tuple to support
Iron Condors, Credit Spreads, Ratio Spreads, etc.

OI and daily volume are still captured and stored on ``LiquidityProfile``
for the per-leg explorer columns, but they no longer drive the headline
``liquidity`` scalar shown in the dashboard table.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LiquidityProfile:
    """Aggregated liquidity profile for a Reverse BWB combo."""

    liquidity: int          # MIN(bid_size_leg / abs(ratio_leg))
    minimum_open_interest: int  # set = liquidity so UI "v" suffix never shown
    minimum_volume: int
    oi_legs: tuple[int | None, int | None, int | None]
    vol_legs: tuple[int | None, int | None, int | None]
    bid_size_legs: tuple[int | None, int | None, int | None]


def compute_liquidity_profile(
    *,
    bid_size_legs: tuple[int | None, int | None, int | None],
    ratios: tuple[int, int, int] = (1, 2, 1),
    oi_legs: tuple[int | None, int | None, int | None] = (None, None, None),
    vol_legs: tuple[int | None, int | None, int | None] = (None, None, None),
) -> LiquidityProfile:
    """Build the per-combo liquidity profile from raw per-leg bid sizes.

    Core formula (generic, strategy-independent):

        Capacity_i = BidSize_i / abs(Ratio_i)
        Liquidity  = MIN(Capacity_i)   across all legs with known bid size

    A leg with ``bid_size = None`` (IBKR did not return data) is skipped
    rather than treated as zero so that a single missing tick does not
    incorrectly kill the opportunity.  If *all* legs are None the result
    is 0 (no executable depth observed).

    ``oi_legs`` and ``vol_legs`` are stored for the per-leg explorer
    columns and the OI floor filter but do not affect the headline value.
    """
    capacities: list[float] = []
    for bid_size, ratio in zip(bid_size_legs, ratios):
        if bid_size is not None and ratio != 0:
            capacities.append(max(0, bid_size) / abs(ratio))

    liquidity = int(min(capacities)) if capacities else 0

    vol_values = [v for v in vol_legs if v is not None]
    min_vol = min(vol_values) if vol_values else 0

    return LiquidityProfile(
        liquidity=max(0, liquidity),
        # Set equal to liquidity so the frontend "v" (volume-proxy) suffix
        # is never triggered — bid-size is live market depth, not a proxy.
        minimum_open_interest=max(0, liquidity),
        minimum_volume=max(0, int(min_vol)),
        oi_legs=oi_legs,
        vol_legs=vol_legs,
        bid_size_legs=bid_size_legs,
    )


def meets_liquidity_floor(
    profile: LiquidityProfile,
    *,
    min_leg_oi: int,
) -> bool:
    """Whether each leg meets the configured minimum OI floor.

    A single illiquid leg kills the whole combo.  ``None`` OI means IBKR
    did not return generic ticks for that leg — treated as *unknown*, not
    zero, so we do not reject solely on missing data.
    """
    if min_leg_oi <= 0:
        return True
    for oi in profile.oi_legs:
        if oi is not None and oi < min_leg_oi:
            return False
    return True
