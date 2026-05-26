"""Body-danger zone for a Reverse-BWB credit structure.

For a Reverse Broken-Wing-Butterfly we collect a credit and bear maximum loss
inside the short-strike pair (the "body"). With no live chain we approximate
the body as a band centered on the last close with a half-width of
``0.6 * sigma_horizon`` — a conservative single-sigma fraction.
"""

from __future__ import annotations


def body_danger_zone(
    last_close: float,
    daily_vol_pct: float,
    horizon_days: int,
    half_width_sigma: float = 0.6,
) -> dict[str, float | str]:
    """Return body bounds and a Low/Medium/High label keyed to spot's position inside it."""
    sigma_pct = max(daily_vol_pct * (horizon_days ** 0.5), 0.05)
    half_width = half_width_sigma * sigma_pct / 100.0
    lo = round(last_close * (1.0 - half_width), 2)
    hi = round(last_close * (1.0 + half_width), 2)
    if hi <= lo:
        hi = lo + max(0.01, last_close * 0.001)
    center = (lo + hi) / 2.0
    distance_from_center = abs(last_close - center)
    distance_pct = round(distance_from_center / last_close * 100.0, 3) if last_close else 0.0
    # spot sitting near the center of the body = worst (highest danger)
    half_band = (hi - lo) / 2.0
    in_body_ratio = 1.0 - min(distance_from_center / half_band, 1.0) if half_band > 0 else 1.0
    if in_body_ratio >= 0.7:
        label: str = "High"
    elif in_body_ratio >= 0.35:
        label = "Medium"
    else:
        label = "Low"
    return {
        "short_body_lo": lo,
        "short_body_hi": hi,
        "distance_pct": distance_pct,
        "label": label,
    }
