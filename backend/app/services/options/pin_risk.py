"""Pin-risk heuristic: distance from nearest round-number magnet, normalized by sigma."""

from __future__ import annotations

from collections.abc import Iterable


def _nearest_round(price: float, steps: Iterable[int]) -> tuple[float, float]:
    """Return ``(nearest_round_price, distance_pct)`` across the candidate steps."""
    best_price = price
    best_distance = float("inf")
    for step in steps:
        if step <= 0:
            continue
        candidate = round(price / step) * step
        distance = abs(price - candidate)
        if distance < best_distance:
            best_distance = distance
            best_price = float(candidate)
    if best_distance == float("inf") or price <= 0:
        return float(price), 0.0
    return best_price, round(best_distance / price * 100.0, 3)


def pin_risk(
    last_close: float,
    daily_vol_pct: float,
    horizon_days: int,
    round_steps: Iterable[int] = (5, 10),
) -> dict[str, float | str]:
    """Score 0..1 — higher means closer to a magnet relative to expected move.

    Rule of thumb: if the nearest round-number strike is within ``0.3 *
    sigma_horizon`` of spot, pin risk is HIGH; within 0.7σ it is MEDIUM; else LOW.
    """
    nearest, distance_pct = _nearest_round(last_close, round_steps)
    sigma_pct = max(daily_vol_pct * (horizon_days ** 0.5), 0.05)
    ratio = distance_pct / sigma_pct if sigma_pct > 0 else 1.0
    if ratio <= 0.3:
        label: str = "High"
        score = round(min(1.0, 0.85 + (0.3 - ratio) * 0.5), 3)
    elif ratio <= 0.7:
        label = "Medium"
        score = round(0.45 + (0.7 - ratio) * 0.8, 3)
    else:
        label = "Low"
        score = round(max(0.0, 0.3 - (ratio - 0.7) * 0.3), 3)
    return {
        "score": score,
        "label": label,
        "nearest_round": round(nearest, 2),
        "distance_pct": distance_pct,
    }
