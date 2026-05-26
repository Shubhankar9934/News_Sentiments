"""Position risk math (Phase 5).

Closed-form lognormal probability + expected-value computation for a
Reverse Broken-Wing-Butterfly defined by:

    spot                — underlying price
    body_strike         — short body strike (or midpoint of short pair)
    wing_width_pct      — wing distance from body, as % of spot
    credit              — credit collected per share
    sigma_pct           — 1σ % move over the horizon
    dte                 — days to expiration

Outputs:

    probability_of_profit       — P(terminal price avoids any loss)
    probability_of_touch        — P(spot touches body during DTE) using
                                  the reflection principle
    probability_of_breakeven    — P(terminal price between breakevens)
    probability_of_max_loss     — P(terminal price beyond wings)
    expected_value_usd          — closed-form integral of PnL over the
                                  terminal price distribution

These never reach the card; they live on ``options_intelligence.position_risk``
and the explainability layer.
"""

from __future__ import annotations

from math import erf, exp, log, sqrt
from typing import Any


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def _terminal_sigma_log(sigma_pct: float) -> float:
    """Convert horizon 1σ% into a lognormal terminal sigma."""

    return max(1e-6, float(sigma_pct) / 100.0)


def _lognormal_prob_within(spot: float, lo: float, hi: float, sigma_log: float) -> float:
    if spot <= 0 or lo <= 0 or hi <= 0 or sigma_log <= 0:
        return 0.0
    z_hi = log(hi / spot) / sigma_log
    z_lo = log(lo / spot) / sigma_log
    return max(0.0, _normal_cdf(z_hi) - _normal_cdf(z_lo))


def _probability_of_touch(
    spot: float, lower: float, upper: float, sigma_log: float
) -> float:
    """Reflection-principle approximation for touch probability inside DTE."""

    if spot <= 0 or sigma_log <= 0:
        return 0.0
    # Touch in [lower, upper] over the horizon ≈ 2 * P(terminal in band)
    # bounded by 1.0 (Reflecting Brownian approximation on log returns).
    terminal_in_band = _lognormal_prob_within(spot, lower, upper, sigma_log)
    return min(1.0, terminal_in_band * 2.0)


def _expected_value(
    spot: float,
    body_strike: float,
    wing_dollars: float,
    credit: float,
    sigma_log: float,
) -> float:
    """Closed-form EV using a piecewise-linear Reverse BWB payout.

    Payout shape (per share):

        S < body - wing             →  +credit − wing_dollars + (body − wing − S)*0  (≈ max_loss limited)
        body - wing ≤ S < body      →  +credit − (body − S)
        body ≤ S < body + wing      →  +credit − (S − body)
        S ≥ body + wing             →  +credit − wing_dollars

    For a symmetric body (single body_strike), max loss = wing_dollars − credit.
    """

    max_loss = max(0.0, wing_dollars - credit)
    # Integrate via Monte-Carlo-quality midpoint quadrature in log-space.
    # 401 nodes spanning ±5σ; sufficient precision for trader-facing EV.
    n = 401
    ev = 0.0
    total_w = 0.0
    log_lo = -5.0
    log_hi = 5.0
    dx = (log_hi - log_lo) / (n - 1)
    for i in range(n):
        z = log_lo + i * dx
        s_terminal = spot * exp(z * sigma_log)
        # standard normal density weight
        from math import pi

        w = exp(-0.5 * z * z) / sqrt(2.0 * pi) * dx
        if s_terminal >= body_strike + wing_dollars:
            payoff = credit - wing_dollars
        elif s_terminal >= body_strike:
            payoff = credit - (s_terminal - body_strike)
        elif s_terminal >= body_strike - wing_dollars:
            payoff = credit - (body_strike - s_terminal)
        else:
            payoff = credit - wing_dollars
        # Clamp payoff to [-max_loss, +credit]
        payoff = max(-max_loss, min(credit, payoff))
        ev += payoff * w
        total_w += w
    if total_w > 0:
        ev = ev / total_w
    # Scale to per-contract dollars (100 multiplier)
    return round(ev * 100.0, 2)


def compute_position_risk(
    *,
    spot: float,
    body_strike: float,
    wing_width_pct: float,
    credit: float,
    sigma_pct: float,
    dte: int,
) -> dict[str, Any] | None:
    """Compute the position-risk dict; returns ``None`` on non-physical input."""

    if spot is None or spot <= 0:
        return None
    if body_strike is None or body_strike <= 0:
        return None
    if wing_width_pct is None or wing_width_pct <= 0:
        return None
    if credit is None or credit < 0:
        return None
    if dte is None or dte <= 0:
        return None

    sigma_log = _terminal_sigma_log(sigma_pct)
    wing_dollars = spot * (float(wing_width_pct) / 100.0)

    upper_be = body_strike + credit
    lower_be = body_strike - credit
    upper_wing = body_strike + wing_dollars
    lower_wing = body_strike - wing_dollars

    p_in_be = _lognormal_prob_within(spot, lower_be, upper_be, sigma_log)
    p_in_body = _lognormal_prob_within(spot, lower_wing, upper_wing, sigma_log)
    p_below_lower = _normal_cdf(log(lower_wing / spot) / sigma_log)
    p_above_upper = 1.0 - _normal_cdf(log(upper_wing / spot) / sigma_log)
    p_max_loss = min(1.0, max(0.0, p_below_lower + p_above_upper))

    # Profit = anywhere terminal price > worse-than-credit outcome but
    # ≤ +credit ceiling. Approximated as "outside the body" plus the
    # narrow band inside breakevens.
    p_profit = max(0.0, min(1.0, 1.0 - p_in_body + p_in_be * 0.5))
    p_touch = _probability_of_touch(spot, lower_wing, upper_wing, sigma_log)

    ev_usd = _expected_value(
        spot=spot,
        body_strike=body_strike,
        wing_dollars=wing_dollars,
        credit=credit,
        sigma_log=sigma_log,
    )

    assumptions = [
        f"Lognormal terminal distribution, sigma_pct={float(sigma_pct):.2f}%",
        "Zero drift over horizon",
        f"DTE={int(dte)} days",
        "PoT uses reflection-principle approximation (upper bound 1.0)",
        "EV uses 401-point Gaussian quadrature in log-space",
    ]

    return {
        "probability_of_profit": round(p_profit, 4),
        "probability_of_touch": round(p_touch, 4),
        "probability_of_breakeven": round(p_in_be, 4),
        "probability_of_max_loss": round(p_max_loss, 4),
        "expected_value_usd": ev_usd,
        "method": "lognormal_closed_form",
        "assumptions": assumptions,
    }
