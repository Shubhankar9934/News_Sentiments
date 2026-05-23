"""Tests for thesis clustering."""

from __future__ import annotations

from app.services.deliberation.schemas import IndependentOpinion, ReasoningStep
from app.services.deliberation.scoring.thesis_clustering import build_thesis_clusters


def test_panel_groups_by_stance():
    round1 = {
        "gpt": IndependentOpinion(
            model="gpt",
            stance="mixed",
            confidence=0.60,
            reasoning_steps=[ReasoningStep(step=1, title="Trade Desk warning on ad market", analysis="...")],
        ),
        "groq": IndependentOpinion(
            model="groq",
            stance="bullish",
            confidence=0.65,
            reasoning_steps=[ReasoningStep(step=1, title="Nvidia AI demand tailwind", analysis="...")],
        ),
        "claude": IndependentOpinion(
            model="claude",
            stance="neutral",
            confidence=0.52,
            reasoning_steps=[ReasoningStep(step=1, title="Range-bound on macro", analysis="...")],
        ),
        "deepseek": IndependentOpinion(
            model="deepseek",
            stance="mixed",
            confidence=0.55,
            reasoning_steps=[ReasoningStep(step=1, title="Trade Desk red flag", analysis="...")],
        ),
    }
    clusters = build_thesis_clusters(round1)
    by_stance = {c.stance: c for c in clusters}
    assert sorted(by_stance["mixed"].models) == ["deepseek", "gpt"]
    assert by_stance["mixed"].support_count == 2
    assert by_stance["bullish"].models == ["groq"]
    assert by_stance["neutral"].models == ["claude"]


def test_dominant_cluster_renders_first():
    round1 = {
        "gpt": IndependentOpinion(model="gpt", stance="mixed", confidence=0.6),
        "deepseek": IndependentOpinion(model="deepseek", stance="mixed", confidence=0.6),
        "claude": IndependentOpinion(model="claude", stance="bullish", confidence=0.6),
    }
    clusters = build_thesis_clusters(round1)
    assert clusters[0].stance == "mixed"
    assert clusters[0].support_count == 2


def test_entity_summary_extracted_from_reasoning():
    round1 = {
        "gpt": IndependentOpinion(
            model="gpt",
            stance="mixed",
            confidence=0.6,
            reasoning_steps=[
                ReasoningStep(step=1, title="Trade Desk warning", analysis="Trade Desk's red flag on ad market is the most material risk")
            ],
            key_risks=["Trade Desk ad market warning"],
        ),
    }
    clusters = build_thesis_clusters(round1)
    summary = clusters[0].summary.lower()
    # Domain entities should surface in the summary.
    assert "trade desk" in summary
    assert "ad market" in summary


def test_errored_models_excluded():
    round1 = {
        "gpt": IndependentOpinion(model="gpt", stance="mixed", confidence=0.0, error="boom"),
        "claude": IndependentOpinion(model="claude", stance="bullish", confidence=0.6),
    }
    clusters = build_thesis_clusters(round1)
    members = {m for c in clusters for m in c.models}
    assert "gpt" not in members
    assert "claude" in members
