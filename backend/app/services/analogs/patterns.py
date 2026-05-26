"""Lightweight historical-analog pattern detectors.

We don't have an outcome backtest table yet, so these are heuristics over
existing ``processed_articles`` + ``ohlcv_bars`` rows. They produce
``(headline, match_reason)`` candidates that the AnalogService dedupes and
ranks alongside SQL/semantic results.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

EARNINGS_KEYWORDS = ("earnings", "beat", "miss", "guidance", "results", "quarter")
SELLOFF_HINTS = (
    "sell-the-news",
    "sell the news",
    "post-earnings slump",
    "slumps",
    "drops",
    "falls",
    "tumbles",
    "post-earnings",
)
ROTATION_HINTS = (
    "rotation",
    "rotate",
    "rotating",
    "sector rotation",
    "outperform",
    "underperform",
)


def detect_earnings_beat_sell_off(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mark rows whose headline indicates an earnings beat followed by a sell-off."""
    out: list[dict[str, Any]] = []
    for r in rows:
        head = (r.get("headline") or "").lower()
        if not any(k in head for k in EARNINGS_KEYWORDS):
            continue
        if any(k in head for k in SELLOFF_HINTS):
            out.append({**r, "match_reason": "earnings_beat_sell_off", "match_score": 0.85})
    return out


def detect_sector_rotation(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mark rows that look like a sector-rotation episode."""
    out: list[dict[str, Any]] = []
    for r in rows:
        head = (r.get("headline") or "").lower()
        if any(k in head for k in ROTATION_HINTS):
            out.append({**r, "match_reason": "sector_rotation", "match_score": 0.7})
    return out
