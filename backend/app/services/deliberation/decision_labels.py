"""Map council decisions onto dashboard decisions.

After the Assessment Team / Decision Council split, both layers use the
same vocabulary: ``Enter``, ``Wait``, ``Avoid``. This module only
title-cases the council's all-caps ``ENTER/WAIT/AVOID`` output before it
is written to the dashboard summary row.
"""

from __future__ import annotations

from typing import Literal

TradeDecision = Literal["ENTER", "WAIT", "AVOID"]
DashboardDecision = Literal["Enter", "Wait", "Avoid"]

COUNCIL_TO_DASHBOARD: dict[str, DashboardDecision] = {
    "ENTER": "Enter",
    "WAIT": "Wait",
    "AVOID": "Avoid",
}

DASHBOARD_TO_COUNCIL: dict[str, TradeDecision] = {
    "Enter": "ENTER",
    "Wait": "WAIT",
    "Avoid": "AVOID",
}


def council_to_dashboard(decision: str) -> DashboardDecision:
    """Title-case a council ``ENTER/WAIT/AVOID`` for dashboard storage."""

    key = (decision or "").upper()
    return COUNCIL_TO_DASHBOARD.get(key, "Wait")  # type: ignore[return-value]


def dashboard_to_council(decision: str) -> TradeDecision:
    """Inverse helper for any historical SAFE/WATCH/AVOID payload."""

    if not decision:
        return "WAIT"
    title = decision.strip()
    # Accept either the new ("Enter") or the upper-case ("ENTER") form.
    if title in DASHBOARD_TO_COUNCIL:
        return DASHBOARD_TO_COUNCIL[title]
    upper = title.upper()
    if upper in ("ENTER", "WAIT", "AVOID"):
        return upper  # type: ignore[return-value]
    # Legacy dashboard labels.
    legacy = {"SAFE": "ENTER", "WATCH": "WAIT"}
    return legacy.get(upper, "WAIT")  # type: ignore[return-value]
