"""Log-normal move probabilities derived from realized (or implied) daily vol.

We model ``ln(S_T / S_0) ~ N(mu*T, sigma**2 * T)`` with ``mu = 0`` (driftless)
unless an explicit drift is provided. ``sigma`` is the daily log-return stdev,
``T`` is the holding horizon in trading days.

All functions are pure and synchronous so they can be unit-tested without I/O.
"""

from __future__ import annotations

import math
from statistics import NormalDist

_NORM = NormalDist(0.0, 1.0)


def _to_log_sigma_daily(daily_vol_pct: float) -> float:
    """Convert a percent daily move magnitude to log-return sigma.

    Realized vol from the pipeline is already an absolute-percent measure of
    daily moves. We treat it as a close approximation of the log-return stdev
    (small-move regime: ln(1+x) ~ x for |x| < 0.05).
    """
    sigma = max(daily_vol_pct / 100.0, 0.0005)
    return sigma


def p_move_exceeds(
    daily_vol_pct: float,
    horizon_days: int,
    move_pct: float,
    drift: float = 0.0,
) -> float:
    """P( |return| >= move_pct ) over ``horizon_days`` trading days.

    ``move_pct`` is signed: positive = upside threshold, negative = downside threshold.
    Returns a one-sided tail probability.
    """
    if horizon_days <= 0:
        return 0.0
    sigma = _to_log_sigma_daily(daily_vol_pct) * math.sqrt(horizon_days)
    if sigma <= 0:
        return 0.0
    mu = drift * horizon_days
    threshold = math.log(1.0 + move_pct / 100.0)
    if move_pct >= 0:
        z = (threshold - mu) / sigma
        return float(1.0 - _NORM.cdf(z))
    z = (threshold - mu) / sigma
    return float(_NORM.cdf(z))


def p_in_range(
    daily_vol_pct: float,
    horizon_days: int,
    lo_pct: float,
    hi_pct: float,
    drift: float = 0.0,
) -> float:
    """P( lo_pct <= return <= hi_pct ) over ``horizon_days`` trading days."""
    if horizon_days <= 0 or hi_pct <= lo_pct:
        return 0.0
    sigma = _to_log_sigma_daily(daily_vol_pct) * math.sqrt(horizon_days)
    if sigma <= 0:
        return 0.0
    mu = drift * horizon_days
    z_lo = (math.log(1.0 + lo_pct / 100.0) - mu) / sigma
    z_hi = (math.log(1.0 + hi_pct / 100.0) - mu) / sigma
    return float(_NORM.cdf(z_hi) - _NORM.cdf(z_lo))


def move_probabilities(
    last_close: float,
    daily_vol_pct: float,
    horizon_days: int,
    drift: float = 0.0,
) -> dict[str, float]:
    """Return the canonical ±2% / ±3% / 1σ-range probabilities used by the panel."""
    del last_close  # log-normal model is scale-invariant; kept for symmetry with IV path
    sigma_horizon_pct = daily_vol_pct * math.sqrt(max(horizon_days, 0))
    one_sigma = max(sigma_horizon_pct, 0.05)
    return {
        "p_up_2pct": round(p_move_exceeds(daily_vol_pct, horizon_days, 2.0, drift), 4),
        "p_dn_2pct": round(p_move_exceeds(daily_vol_pct, horizon_days, -2.0, drift), 4),
        "p_up_3pct": round(p_move_exceeds(daily_vol_pct, horizon_days, 3.0, drift), 4),
        "p_dn_3pct": round(p_move_exceeds(daily_vol_pct, horizon_days, -3.0, drift), 4),
        "p_in_range_1sigma": round(
            p_in_range(daily_vol_pct, horizon_days, -one_sigma, one_sigma, drift), 4
        ),
    }
