"""Explicit, deterministic ranking score for Reverse BWB opportunities.

The score is a sort key only — nothing is filtered or hidden because of
it. The formula (from the Workstation spec) is:

    score =
        credit_efficiency  * 0.40
      + log1p(liquidity)   * 0.30
      - margin_penalty     * 0.20
      - pin_risk_penalty   * 0.10

Penalties are normalized so the weights stay comparable across tickers:

    margin_penalty   = margin / median_margin_for_ticker     (clamped >=0)
    pin_risk_penalty = |body - underlying| / underlying       (in [0, 1])

The median margin is computed once per (ticker, side) so the same combo
will land in the same position deterministically given the same chain
snapshot. The score is rounded to 6 decimals to keep the JSON payload
stable across recomputes.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass


@dataclass
class _ScoreInputs:
    credit_efficiency: float  # percent (0..100+)
    liquidity: int  # raw min OI
    margin: float  # init margin dollars
    median_margin: float
    body_strike: float
    underlying_price: float


def _pin_risk_penalty(body_strike: float, underlying_price: float) -> float:
    if underlying_price <= 0:
        return 0.0
    distance = abs(body_strike - underlying_price)
    pct = distance / underlying_price
    return float(min(1.0, max(0.0, pct)))


def _margin_penalty(margin: float, median_margin: float) -> float:
    if median_margin <= 0:
        return 0.0
    return float(max(0.0, margin / median_margin))


def _liquidity_term(liquidity: int) -> float:
    return float(math.log1p(max(0, int(liquidity))))


def compute_ranking_score(inp: _ScoreInputs) -> float:
    raw = (
        inp.credit_efficiency * 0.40
        + _liquidity_term(inp.liquidity) * 0.30
        - _margin_penalty(inp.margin, inp.median_margin) * 0.20
        - _pin_risk_penalty(inp.body_strike, inp.underlying_price) * 0.10
    )
    return round(float(raw), 6)


@dataclass
class RankingInput:
    """Minimal payload to score one candidate."""

    credit_efficiency: float  # percent
    liquidity: int  # min OI
    margin: float  # dollars
    body_strike: float
    underlying_price: float


def score_candidates(
    candidates: list[RankingInput],
) -> list[float]:
    """Compute ranking scores for a batch using batch-level normalization.

    Returns scores in the same order as ``candidates``. An empty input
    returns an empty list. ``median_margin`` is computed across the batch
    so identical chains always rank the same combos at the same positions.
    """
    if not candidates:
        return []

    margins = [c.margin for c in candidates if c.margin and c.margin > 0]
    median_margin = float(statistics.median(margins)) if margins else 0.0

    out: list[float] = []
    for c in candidates:
        out.append(
            compute_ranking_score(
                _ScoreInputs(
                    credit_efficiency=float(c.credit_efficiency),
                    liquidity=int(c.liquidity),
                    margin=float(c.margin),
                    median_margin=median_margin,
                    body_strike=float(c.body_strike),
                    underlying_price=float(c.underlying_price),
                )
            )
        )
    return out
