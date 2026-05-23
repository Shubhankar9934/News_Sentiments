"""Tests for the disagreement topology engine."""

from __future__ import annotations

from app.services.deliberation.schemas import IndependentOpinion, ReasoningStep
from app.services.deliberation.scoring.disagreement import build_disagreement_matrix
from app.services.deliberation.scoring.risk_clustering import cluster_risks
from app.services.deliberation.scoring.topology import (
    build_conviction_heatmap,
    build_disagreement_topology,
)


def _panel():
    return {
        "gpt": IndependentOpinion(
            model="gpt",
            stance="mixed",
            confidence=0.60,
            time_horizon="1-3d",
            reasoning_steps=[
                ReasoningStep(step=1, title="Macro", analysis="Nvidia earnings tailwind"),
            ],
            key_risks=["Trade Desk ad market warning"],
        ),
        "groq": IndependentOpinion(
            model="groq",
            stance="bullish",
            confidence=0.65,
            time_horizon="1-3d",
            reasoning_steps=[
                ReasoningStep(step=1, title="AI demand", analysis="Cloud capex acceleration"),
            ],
            key_risks=["Waymo regulatory pause"],
        ),
        "claude": IndependentOpinion(
            model="claude",
            stance="neutral",
            confidence=0.52,
            time_horizon="1w",
            reasoning_steps=[
                ReasoningStep(step=1, title="Ads", analysis="Trade Desk red flag on digital ad market"),
            ],
            key_risks=["Trade Desk's digital ad market warning could broaden"],
        ),
        "deepseek": IndependentOpinion(
            model="deepseek",
            stance="mixed",
            confidence=0.55,
            time_horizon="1-3d",
            reasoning_steps=[
                ReasoningStep(step=1, title="Macro", analysis="Mixed sentiment, rates pressure"),
            ],
            key_risks=["Trade Desk ad market caution"],
        ),
    }


def test_topology_returns_all_five_axes():
    round1 = _panel()
    matrix = build_disagreement_matrix(round1)
    clusters = cluster_risks(round1, [])
    topology = build_disagreement_topology(round1, matrix, clusters)
    assert set(topology["axes"].keys()) == {
        "directional",
        "confidence",
        "evidence",
        "risk",
        "timing",
    }
    assert 0.0 <= topology["overall"] <= 1.0


def test_directional_axis_high_when_panel_splits():
    round1 = _panel()
    matrix = build_disagreement_matrix(round1)
    clusters = cluster_risks(round1, [])
    topology = build_disagreement_topology(round1, matrix, clusters)
    # 1 bullish + 1 neutral + 2 mixed — should register non-zero directional
    # disagreement, but well below saturation.
    assert topology["axes"]["directional"] > 0.0
    assert topology["axes"]["directional"] < 0.8


def test_timing_axis_when_horizons_match_is_zero():
    round1 = {
        "gpt": IndependentOpinion(model="gpt", stance="bullish", confidence=0.7, time_horizon="1-3d"),
        "claude": IndependentOpinion(model="claude", stance="bullish", confidence=0.6, time_horizon="1-3d"),
    }
    matrix = build_disagreement_matrix(round1)
    topology = build_disagreement_topology(round1, matrix, [])
    assert topology["axes"]["timing"] == 0.0


def test_conviction_heatmap_shape():
    round1 = _panel()
    matrix = build_disagreement_matrix(round1)
    clusters = cluster_risks(round1, [])
    heatmap = build_conviction_heatmap(round1, matrix, clusters)
    assert heatmap["topics"]  # non-empty
    assert sorted(heatmap["models"]) == ["claude", "deepseek", "gpt", "groq"]
    for topic in heatmap["topics"]:
        for model in heatmap["models"]:
            cell = heatmap["cells"][topic][model]
            assert "stance" in cell
            assert "confidence" in cell
            assert "risk_score" in cell
            assert 0.0 <= cell["confidence"] <= 1.0


def test_risk_keyword_no_longer_forces_bearish_topic():
    """Regression test for the substring bug — the word 'risk' alone must
    not flip a topic stance to bearish. Without an explicit directional
    marker the topic should inherit the model's overall stance."""
    from app.services.deliberation.scoring.disagreement import _topic_stance_from_text

    assert _topic_stance_from_text("there is some risk here", "bullish") == "bullish"
    assert _topic_stance_from_text("clearly bearish setup", "bullish") == "bearish"
    assert _topic_stance_from_text("clearly bullish setup", "bearish") == "bullish"


def test_pairwise_contradictions_detected_for_opposing_stances():
    """When two models hold opposite directional stances on the same topic
    the matrix should report `oppose`, and contradictions[] should contain a
    pair_topic entry naming both models."""
    from app.services.deliberation.scoring.topology import detect_contradictions

    round1 = {
        "gpt": IndependentOpinion(
            model="gpt",
            stance="bullish",
            confidence=0.7,
            reasoning_steps=[
                ReasoningStep(
                    step=1, title="Macro", analysis="Bullish macro: Fed pivot tailwind"
                )
            ],
        ),
        "claude": IndependentOpinion(
            model="claude",
            stance="bearish",
            confidence=0.6,
            reasoning_steps=[
                ReasoningStep(
                    step=1, title="Macro", analysis="Bearish macro: rates headwind dominant"
                )
            ],
        ),
    }
    matrix = build_disagreement_matrix(round1)
    clusters = cluster_risks(round1, [])
    contradictions = detect_contradictions(round1, matrix, clusters, reasoning_overlap=0.4)
    pair_topic = [c for c in contradictions if c["type"] == "pair_topic"]
    assert pair_topic, "expected at least one pair_topic contradiction"
    pair = pair_topic[0]
    assert {pair["model_a"], pair["model_b"]} == {"gpt", "claude"}
    assert {pair["stance_a"], pair["stance_b"]} == {"bullish", "bearish"}
    assert pair["severity"] == "high"


def test_confidence_vs_reasoning_contradiction_when_overlap_low():
    from app.services.deliberation.scoring.topology import detect_contradictions

    round1 = {
        "gpt": IndependentOpinion(model="gpt", stance="bullish", confidence=0.85),
        "claude": IndependentOpinion(model="claude", stance="neutral", confidence=0.5),
    }
    matrix = build_disagreement_matrix(round1)
    clusters = cluster_risks(round1, [])
    contradictions = detect_contradictions(round1, matrix, clusters, reasoning_overlap=0.05)
    high_conf = [c for c in contradictions if c["type"] == "confidence_vs_reasoning"]
    assert any(c["model_a"] == "gpt" for c in high_conf)
