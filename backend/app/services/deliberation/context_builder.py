"""Build structured deliberation context from a completed research report.

PR10 — token-budgeted compression. Earlier the context dumped up to 30
``article_evidence`` rows verbatim, which dominated the LLM input on
high-news days. We now rank evidence by ``impact_score`` and ``reliability``,
keep top-k entries, and drop low-signal fields (long URLs, ``ai_summary``
duplicates) when the running token estimate exceeds ``DIL_CONTEXT_TOKEN_BUDGET``.
"""

from __future__ import annotations

import json
from typing import Any

from app.core.config import settings as global_settings
from app.services.deliberation.schemas import DeliberationContext


_EVIDENCE_HARD_CAP = 30  # absolute cap regardless of budget
_EVIDENCE_KEEP_KEYS = (
    "headline",
    "source",
    "published_at",
    "impact_score",
    "sentiment_label",
    "sentiment_score",
    "reliability_score",
    "event_type",
    "abnormal_return",
)


def _approx_token_count(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def _rank_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort by impact * reliability descending; ties broken by recency."""

    def score(row: dict[str, Any]) -> float:
        impact = float(row.get("impact_score") or 0.0)
        rel = float(row.get("reliability_score") or 0.5)
        return impact * (0.5 + 0.5 * rel)

    return sorted(evidence, key=lambda r: (-score(r), r.get("published_at") or ""))


def _trim_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: row[k] for k in _EVIDENCE_KEEP_KEYS if k in row and row[k] is not None}


def _budget_evidence(
    evidence: list[dict[str, Any]],
    *,
    token_budget: int,
) -> list[dict[str, Any]]:
    """Greedy trim: keep rows in ranked order while the running token
    estimate stays under budget. Always keep at least 5 rows so the LLM
    has *some* concrete grounding even on token-tight runs."""
    ranked = _rank_evidence(evidence)[:_EVIDENCE_HARD_CAP]
    if not ranked:
        return []
    trimmed = [_trim_row(r) for r in ranked]
    running = 0
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(trimmed):
        approx = _approx_token_count(json.dumps(row, default=str))
        if idx < 5 or running + approx <= token_budget:
            out.append(row)
            running += approx
        else:
            break
    return out


def build_deliberation_context(report: dict[str, Any], ticker: str) -> DeliberationContext:
    meta = report.get("_pipeline_meta") or {}
    raw_evidence = meta.get("article_evidence") or []
    token_budget = getattr(global_settings, "dil_context_token_budget", 6000)
    # Reserve part of the budget for narrative / market context; let the
    # evidence list take roughly two-thirds of the total.
    evidence_budget = max(800, int(token_budget * 0.66))
    article_evidence = _budget_evidence(raw_evidence, token_budget=evidence_budget)

    return DeliberationContext(
        ticker=ticker.upper(),
        market_context={
            "price_prediction": report.get("price_prediction") or {},
            "price_snapshot": meta.get("price_snapshot") or {},
            "volatility_regime": meta.get("volatility_regime"),
        },
        sentiment={
            "overall_sentiment_score": report.get("overall_sentiment_score"),
            "overall_sentiment_label": report.get("overall_sentiment_label"),
            "sentiment_breakdown": report.get("sentiment_breakdown") or [],
        },
        narrative={
            "dominant_narrative": report.get("dominant_narrative"),
            "what_happened": report.get("what_happened"),
            "price_movers": report.get("price_movers"),
        },
        key_events=report.get("key_events") or [],
        source_reliability=report.get("source_reliability") or [],
        historical_analogs=[],
        article_evidence=article_evidence,
        top_impact_events=meta.get("top_impact_events") or [],
        evidence_summary={
            "articles_analyzed": report.get("articles_analyzed"),
            "unique_sources": report.get("unique_sources"),
            "data_quality_note": report.get("data_quality_note"),
            "evidence_kept": len(article_evidence),
            "evidence_total": len(raw_evidence),
        },
    )
