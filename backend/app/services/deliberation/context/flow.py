"""Options flow heuristics from chain / volume data."""

from __future__ import annotations

from typing import Any


def build_flow_context(
    price_snapshot: dict[str, Any],
    options_intelligence: dict[str, Any] | None,
) -> dict[str, Any]:
    vol_ratio = price_snapshot.get("volume_vs_avg")
    oi = options_intelligence or {}
    pin = oi.get("pin_risk") or {}

    unusual = False
    signals: list[str] = []
    if vol_ratio is not None and vol_ratio >= 1.5:
        unusual = True
        signals.append(f"Equity volume {vol_ratio}x 20d average")
    if pin.get("label") == "High":
        signals.append(f"Pin risk elevated near {pin.get('nearest_round')}")

    return {
        "unusual_activity": unusual,
        "signals": signals,
        "volume_vs_avg": vol_ratio,
        "pin_risk_label": pin.get("label"),
        "note": "v1 heuristic — chain UOA z-scores when live chain available",
    }
