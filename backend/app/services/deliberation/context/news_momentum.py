"""News sentiment momentum over recent evidence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any


def build_news_momentum(article_evidence: list[dict[str, Any]]) -> dict[str, Any]:
    if not article_evidence:
        return {"label": "unknown", "bullish_count": 0, "bearish_count": 0}

    cutoff = datetime.now(UTC) - timedelta(hours=48)
    recent: list[dict[str, Any]] = []
    older: list[dict[str, Any]] = []

    for row in article_evidence:
        pub = row.get("published_at")
        try:
            if isinstance(pub, str):
                dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            else:
                dt = cutoff - timedelta(days=1)
        except (ValueError, TypeError):
            dt = cutoff - timedelta(days=1)
        if dt >= cutoff:
            recent.append(row)
        else:
            older.append(row)

    def _sentiment_bucket(rows: list[dict[str, Any]]) -> tuple[int, int, int]:
        bull = bear = neutral = 0
        for r in rows:
            label = (r.get("sentiment_label") or "").lower()
            if "bull" in label:
                bull += 1
            elif "bear" in label:
                bear += 1
            else:
                neutral += 1
        return bull, bear, neutral

    r_bull, r_bear, _ = _sentiment_bucket(recent)
    o_bull, o_bear, _ = _sentiment_bucket(older)

    momentum = (r_bull - r_bear) - (o_bull - o_bear)
    if momentum >= 2:
        label = "accelerating_bullish"
    elif momentum <= -2:
        label = "accelerating_bearish"
    elif r_bull > r_bear:
        label = "bullish_drift"
    elif r_bear > r_bull:
        label = "bearish_drift"
    else:
        label = "neutral"

    return {
        "label": label,
        "momentum_score": momentum,
        "bullish_count_48h": r_bull,
        "bearish_count_48h": r_bear,
        "articles_48h": len(recent),
        "narrative_shift": "bullish" if momentum > 0 else "bearish" if momentum < 0 else "stable",
    }
