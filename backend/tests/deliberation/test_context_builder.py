"""Tests for PR10 context compression."""

from __future__ import annotations

from app.services.deliberation.context_builder import build_deliberation_context


def _evidence_row(i: int, *, impact: float = 0.5, reliability: float = 0.7) -> dict:
    return {
        "headline": f"Headline {i} — some moderately long text describing an event",
        "source": f"source{i}.com",
        "url": f"https://source{i}.com/article-{i}-with-a-very-long-slug-that-eats-tokens",
        "published_at": f"2026-05-22T{i:02d}:00:00Z",
        "impact_score": impact,
        "sentiment_label": "Mixed",
        "sentiment_score": 0.1,
        "reliability_score": reliability,
        "event_type": "earnings" if i % 2 == 0 else None,
        "ai_summary": "Long summary text " * 30,  # filler to balloon token count
    }


def test_evidence_is_ranked_by_impact_and_reliability():
    rows = [
        _evidence_row(1, impact=0.1, reliability=0.5),
        _evidence_row(2, impact=0.9, reliability=0.9),
        _evidence_row(3, impact=0.5, reliability=0.5),
    ]
    report = {"_pipeline_meta": {"article_evidence": rows}}
    ctx = build_deliberation_context(report, "AAPL")
    headlines = [r["headline"] for r in ctx.article_evidence]
    assert headlines[0].startswith("Headline 2")


def test_evidence_trimmed_under_token_budget():
    rows = [_evidence_row(i) for i in range(1, 31)]
    report = {"_pipeline_meta": {"article_evidence": rows}}
    ctx = build_deliberation_context(report, "AAPL")
    # We always keep at least 5 rows for grounding, even with low budget.
    assert len(ctx.article_evidence) >= 5
    # The trimmed rows must not contain heavy fields like ``ai_summary`` /
    # ``url`` which the compression layer strips.
    for row in ctx.article_evidence:
        assert "ai_summary" not in row
        assert "url" not in row


def test_legacy_back_compat_minimal_report():
    ctx = build_deliberation_context({}, "AAPL")
    assert ctx.ticker == "AAPL"
    assert ctx.article_evidence == []
    assert ctx.evidence_summary["evidence_total"] == 0
