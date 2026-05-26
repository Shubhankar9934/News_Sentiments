"""1-sigma expected price range over the configured horizon."""

from __future__ import annotations

import math


def expected_range(
    last_close: float,
    daily_vol_pct: float,
    horizon_days: int,
    z: float = 1.0,
    data_quality_penalty: float = 0.0,
) -> dict[str, float]:
    """Return a ``{low, high, sigma_pct, confidence}`` band.

    ``z`` selects the sigma multiplier; ``data_quality_penalty`` ∈ [0,1] is
    subtracted from the base confidence (e.g. low article count, mock data).
    """
    sigma_pct = max(daily_vol_pct, 0.05) * math.sqrt(max(horizon_days, 0))
    pct_move = (z * sigma_pct) / 100.0
    low = round(last_close * (1.0 - pct_move), 2)
    high = round(last_close * (1.0 + pct_move), 2)
    base_conf = 0.68 if z == 1.0 else 0.95 if z == 2.0 else min(0.5 + 0.18 * z, 0.99)
    confidence = max(0.0, min(1.0, base_conf - data_quality_penalty))
    return {
        "low": low,
        "high": high,
        "sigma_pct": round(sigma_pct, 3),
        "confidence": round(confidence, 3),
    }
