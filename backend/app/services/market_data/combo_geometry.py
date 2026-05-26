"""Reverse Broken-Wing Butterfly strike construction.

Two callers share this module:

    1. ``app.services.dashboard.opportunity_generator`` — placeholder
       generator. Used when IBKR is offline or in tests.
    2. ``app.services.market_data.options_opportunity_service`` — live
       generator. Maps each candidate to real IBKR option contracts and
       prices.

Keeping the strike geometry in one place ensures the placeholder and the
live source converge to the *same* candidate set. Only the premium /
margin / liquidity values differ between paths.

Reverse BWB notation: ``long_wing_a / short_body / long_wing_b`` — three
strikes, four legs (the short body is doubled). The combo is the classic
broken-wing butterfly:

    BUY  long_wing_a   x 1
    SELL short_body    x 2
    BUY  long_wing_b   x 1

For CALL combos the strikes descend (e.g. 740 body, 735 / 745 wings); for
PUTs they ascend (e.g. 225 body, 222.5 / 227.5 wings). When the two wings
are equidistant from the body, this collapses to a standard butterfly;
when they differ, the asymmetric leg gives the BWB its name. The
``ReverseBwbCandidate`` carries enough strike geometry to be priced (mid
spread per leg) and margined (deterministic max risk + IBKR WhatIf).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ReverseBwbCandidate:
    """A single (strike-only) Reverse BWB candidate.

    The historical model stored ``(short_inner, long_short, long_outer)``
    matching a 3-leg credit spread. The new Workstation generator uses
    a 4-leg butterfly with a doubled short body:

        BUY  long_wing_a    x 1
        SELL short_body     x 2
        BUY  long_wing_b    x 1

    The legacy aliases (``short_inner``, ``long_short``, ``long_outer``)
    remain as compatibility properties for the small handful of callers
    that still reference them, but new code should use the explicit
    wing/body fields.

    Pricing/margin/liquidity are intentionally absent — those depend on
    the source (placeholder formula vs. live IBKR chain).
    """

    side: str  # "CALL" | "PUT"
    long_wing_a: float
    short_body: float
    long_wing_b: float
    wing_left: float = 0.0
    wing_right: float = 0.0
    offset_sigma: float = 0.0  # offset of short_body from spot in sigma units

    @classmethod
    def from_strikes(
        cls,
        *,
        side: str,
        long_wing_a: float,
        short_body: float,
        long_wing_b: float,
        offset_sigma: float = 0.0,
    ) -> "ReverseBwbCandidate":
        wing_left = abs(long_wing_a - short_body)
        wing_right = abs(long_wing_b - short_body)
        return cls(
            side=side.upper(),
            long_wing_a=float(long_wing_a),
            short_body=float(short_body),
            long_wing_b=float(long_wing_b),
            wing_left=float(wing_left),
            wing_right=float(wing_right),
            offset_sigma=float(offset_sigma),
        )

    # ----------------------------------------------------------- legacy aliases
    # Older code referenced these names; we map them onto the new geometry so
    # nothing breaks while the rest of the codebase migrates.
    @property
    def short_inner(self) -> float:
        return self.long_wing_a

    @property
    def long_short(self) -> float:
        return self.short_body

    @property
    def long_outer(self) -> float:
        return self.long_wing_b

    @property
    def wing_width(self) -> float:
        # Average wing distance — convenient single scalar for legacy
        # max-risk estimates.
        if self.wing_left and self.wing_right:
            return (self.wing_left + self.wing_right) / 2.0
        return max(self.wing_left, self.wing_right, abs(self.short_body - self.long_wing_a))

    def combo_label(self) -> str:
        return _format_combo(self.long_wing_a, self.short_body, self.long_wing_b)

    @property
    def strikes(self) -> tuple[float, float, float]:
        return (self.long_wing_a, self.short_body, self.long_wing_b)

    @property
    def max_risk(self) -> float:
        """Max loss per spread (per share, before x100 multiplier).

        For a 4-leg BWB the max risk equals the wider wing distance from
        the body. Symmetric wings -> equal to wing width; asymmetric ->
        the larger of the two wings dominates.
        """
        return max(self.wing_left, self.wing_right)


# --------------------------------------------------------------------------
# Strike rounding
# --------------------------------------------------------------------------
def strike_step(price: float) -> float:
    """Snap step matching the most common IBKR option strike grid."""
    if price >= 500:
        return 5.0
    if price >= 100:
        return 1.0
    if price >= 25:
        return 0.5
    return 0.5


def round_strike(price: float, step: float) -> float:
    if step <= 0:
        step = 0.5
    return round(price / step) * step


# --------------------------------------------------------------------------
# Candidate construction
# --------------------------------------------------------------------------
def build_candidates(
    *,
    side: str,
    last_close: float,
    sigma_dollars: float,
    step: float,
    offsets_sigma: tuple[float, ...] = (0.5, 1.0),
) -> list[ReverseBwbCandidate]:
    """Build N Reverse BWB candidates for one side (legacy 2-per-side path).

    Retained for the placeholder snapshot generator. The Workstation live
    generator uses :func:`enumerate_candidates` instead, which produces
    every valid (long_wing_a, short_body, long_wing_b) triplet within the
    configured wing-width bounds.
    """
    if last_close <= 0 or sigma_dollars <= 0:
        return []

    sign = 1 if side.upper() == "CALL" else -1
    out: list[ReverseBwbCandidate] = []
    for offset_sigma in offsets_sigma:
        anchor = last_close + sign * offset_sigma * sigma_dollars
        short_body = round_strike(anchor, step)
        wing_width = max(step, round_strike(0.5 * sigma_dollars, step))
        # Long wing A sits one wing-width on the spot-side of the body;
        # long wing B sits one wing-width on the far side.
        long_wing_a = short_body - sign * wing_width
        long_wing_b = short_body + sign * wing_width
        out.append(
            ReverseBwbCandidate.from_strikes(
                side=side.upper(),
                long_wing_a=long_wing_a,
                short_body=short_body,
                long_wing_b=long_wing_b,
                offset_sigma=offset_sigma,
            )
        )
    return out


def enumerate_candidates(
    *,
    side: str,
    strikes: list[float],
    last_close: float,
    wing_min_strikes: int = 1,
    wing_max_strikes: int = 20,
) -> list[ReverseBwbCandidate]:
    """Enumerate every valid Reverse BWB candidate from a real strike chain.

    For each strike on the configured side of the underlying (CALL = at or
    above last_close; PUT = at or below last_close), generate every
    (long_wing_a, short_body, long_wing_b) triplet where:

        * The body strike sits on the correct side of the underlying
          (CALLs => body >= last_close; PUTs => body <= last_close).
        * Both wings live on the same side of the underlying as the body.
        * Wing widths (in strike-index units) fall within
          ``[wing_min_strikes, wing_max_strikes]``.
        * Wings are distinct from each other and from the body.

    Asymmetric wings are allowed — that is the whole point of the
    "broken wing" name. The two wing strikes are sorted so the returned
    label is deterministic regardless of which side is the longer wing.

    Returns:
        A list of candidates with strike geometry filled in. Pricing /
        liquidity / margin / ranking are filled in downstream by the
        opportunity service.
    """
    if not strikes or last_close <= 0:
        return []

    sorted_strikes = sorted({float(s) for s in strikes})
    up = side.upper()

    # Restrict the body universe to the requested side of spot. The body
    # is the magnet of the structure — putting it on the opposite side
    # would yield an unnatural / poorly-defined Reverse BWB.
    if up == "CALL":
        side_strikes = [s for s in sorted_strikes if s >= last_close]
    else:
        side_strikes = [s for s in sorted_strikes if s <= last_close]
    if not side_strikes:
        return []

    # Pre-compute the indices in the SAME-SIDE strike list. Wing widths
    # are expressed in strike-step units against this filtered list, so
    # the search space is bounded regardless of underlying price.
    n = len(side_strikes)
    wmin = max(1, int(wing_min_strikes))
    wmax = max(wmin, int(wing_max_strikes))

    out: list[ReverseBwbCandidate] = []
    for body_idx in range(n):
        body = side_strikes[body_idx]
        for left_w in range(wmin, wmax + 1):
            left_idx = body_idx - left_w
            if left_idx < 0:
                continue
            wing_a = side_strikes[left_idx]
            for right_w in range(wmin, wmax + 1):
                right_idx = body_idx + right_w
                if right_idx >= n:
                    continue
                wing_b = side_strikes[right_idx]
                # Three distinct strikes per BWB.
                if len({wing_a, body, wing_b}) != 3:
                    continue
                # Canonicalize the wing order so the label and dedup key
                # are stable across asymmetric pairs (a == lower-strike
                # wing, b == higher-strike wing).
                lower = min(wing_a, wing_b)
                upper = max(wing_a, wing_b)
                out.append(
                    ReverseBwbCandidate.from_strikes(
                        side=up,
                        long_wing_a=lower,
                        short_body=body,
                        long_wing_b=upper,
                        offset_sigma=0.0,
                    )
                )

    # Deduplicate — symmetric triplets are visited twice as (left, right)
    # and (right, left) iterations.
    seen: set[tuple[float, float, float]] = set()
    deduped: list[ReverseBwbCandidate] = []
    for cand in out:
        key = (cand.long_wing_a, cand.short_body, cand.long_wing_b)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cand)
    return deduped


def expiry_label(dte: int) -> str:
    if dte <= 1:
        return "0D"
    return f"{int(dte)}D"


def derive_dte_pair(horizon_days: int | float | None) -> tuple[int, int]:
    """Return ``(dte_short, dte_long)`` mirroring the placeholder generator.

    ``dte_short`` clamps to >=1; ``dte_long`` is ~2.5x ``dte_short`` with a
    minimum spacing of 3 days.
    """
    if horizon_days is None:
        horizon_days = 2
    dte_short = max(1, int(round(float(horizon_days))))
    dte_long = max(dte_short + 3, int(math.ceil(dte_short * 2.5)))
    return dte_short, dte_long


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _format_combo(long_wing_a: float, short_body: float, long_wing_b: float) -> str:
    """Format a Reverse BWB combo as ``wingA/body/wingB`` with smart precision."""

    def _fmt(v: float) -> str:
        if abs(v - round(v)) < 1e-6:
            return f"{int(round(v))}"
        return f"{v:.1f}"

    return f"{_fmt(long_wing_a)}/{_fmt(short_body)}/{_fmt(long_wing_b)}"


def numeric_liquidity(
    *,
    oi_leg1: int | None,
    oi_leg2: int | None,
    oi_leg3: int | None,
) -> int:
    """Numeric Reverse BWB liquidity = ``min(OI per leg)``.

    Liquidity is a pure number — never a string. ``None`` legs count as
    zero so a missing OI never silently inflates the liquidity score.
    """
    values = [oi_leg1 or 0, oi_leg2 or 0, oi_leg3 or 0]
    return max(0, int(min(values)))


def grade_liquidity(
    *,
    oi_min: int | None,
    vol_min: int | None,
    spread_pct: float | None,
) -> str:
    """Legacy categorical liquidity grade.

    Retained ONLY for the placeholder snapshot generator (which still
    surfaces a categorical label on the legacy ``ticker_option_opportunities``
    table). The live Reverse BWB Trading Workstation path uses
    :func:`numeric_liquidity` exclusively.

    Heuristics:
        - Excellent : OI >= 1000, vol >= 200, spread <= 1.0%
        - Good      : OI >=  300, vol >=  50, spread <= 2.5%
        - Average   : OI >=  100, vol >=  10, spread <= 5.0%
        - Poor      : everything else / unknown
    """
    if oi_min is None or vol_min is None or spread_pct is None:
        return "Average"

    if oi_min >= 1000 and vol_min >= 200 and spread_pct <= 1.0:
        return "Excellent"
    if oi_min >= 300 and vol_min >= 50 and spread_pct <= 2.5:
        return "Good"
    if oi_min >= 100 and vol_min >= 10 and spread_pct <= 5.0:
        return "Average"
    return "Poor"
