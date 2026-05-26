"""Event-risk score from key_events in the report.

Today we have no live earnings/FOMC calendar feed — we proxy event risk by the
density and severity of ``key_events`` already extracted from the news flow.
The structure leaves room for a real calendar to be plugged in later via
``days_to_next_earnings`` / ``fomc_distance`` keyword args.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

_HIGH_IMPACT_TOKENS: frozenset[str] = frozenset(
    {"earnings", "fomc", "fed", "cpi", "guidance", "merger", "acquisition", "fda"}
)


def _impact_weight(impact: str | None, impact_score: float | None) -> float:
    if isinstance(impact_score, (int, float)) and impact_score > 0:
        return float(min(impact_score, 1.0))
    label = (impact or "").lower()
    if label.startswith("high"):
        return 0.8
    if label.startswith("med"):
        return 0.5
    if label.startswith("low"):
        return 0.25
    return 0.4


def event_risk_score(
    key_events: Iterable[dict[str, Any]] | None,
    days_to_next_earnings: int | None = None,
    fomc_distance_days: int | None = None,
) -> dict[str, Any]:
    """Return ``{score: 0..1, label: Low|Medium|High, drivers: [...]}``."""
    drivers: list[str] = []
    score = 0.0

    for ev in list(key_events or [])[:10]:
        text = " ".join(
            [
                str(ev.get("type") or ""),
                str(ev.get("description") or ""),
            ]
        ).lower()
        weight = _impact_weight(ev.get("impact"), ev.get("impact_score"))
        if any(tok in text for tok in _HIGH_IMPACT_TOKENS):
            score = max(score, 0.55 + 0.4 * weight)
            drivers.append((ev.get("description") or ev.get("type") or "key event").strip())
        else:
            score = max(score, 0.2 + 0.3 * weight)

    if isinstance(days_to_next_earnings, int) and 0 <= days_to_next_earnings <= 7:
        score = max(score, 0.85 - 0.05 * days_to_next_earnings)
        drivers.append(f"Earnings in {days_to_next_earnings}d")
    if isinstance(fomc_distance_days, int) and 0 <= fomc_distance_days <= 3:
        score = max(score, 0.7 - 0.1 * fomc_distance_days)
        drivers.append(f"FOMC in {fomc_distance_days}d")

    score = round(min(score, 1.0), 3)
    label = "High" if score >= 0.65 else "Medium" if score >= 0.35 else "Low"
    # dedupe drivers preserving order, cap to 5
    seen: set[str] = set()
    unique_drivers: list[str] = []
    for d in drivers:
        key = d.lower()
        if key and key not in seen:
            seen.add(key)
            unique_drivers.append(d)
        if len(unique_drivers) >= 5:
            break
    return {"score": score, "label": label, "drivers": unique_drivers}
