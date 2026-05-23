"""Tests for deterministic risk clustering."""

from __future__ import annotations

from app.services.deliberation.schemas import DebateCritique, IndependentOpinion
from app.services.deliberation.scoring.risk_clustering import (
    cluster_headlines,
    cluster_risks,
)


def _round1():
    """Models repeat the 'Trade Desk ad market warning' theme four times
    in different phrasings — exactly the failing-example pattern."""
    return {
        "gpt": IndependentOpinion(
            model="gpt",
            stance="mixed",
            confidence=0.60,
            key_risks=[
                "Adverse news from The Trade Desk could undermine Google's ad revenue",
                "Antitrust regulatory overhang remains persistent",
            ],
        ),
        "claude": IndependentOpinion(
            model="claude",
            stance="neutral",
            confidence=0.52,
            key_risks=[
                "Trade Desk's digital ad market warning could broaden into a sector-wide re-rating of ad revenue expectations",
                "Rising U.S. borrowing costs could dampen AI capex",
            ],
            hidden_assumptions=[
                "Assumes Trade Desk's concerns are cyclical rather than structural market share loss",
            ],
        ),
        "deepseek": IndependentOpinion(
            model="deepseek",
            stance="mixed",
            confidence=0.55,
            key_risks=[
                "Trade Desk's ad market caution may signal broader weakness affecting Alphabet's core revenue",
                "Rotation away from megacap tech to smaller AI stocks could weigh on GOOG",
            ],
        ),
        "groq": IndependentOpinion(
            model="groq",
            stance="bullish",
            confidence=0.65,
            key_risks=[
                "Waymo safety pause amplifies negative sentiment around moonshots",
            ],
        ),
    }


def test_paraphrases_collapse_to_one_cluster():
    clusters = cluster_risks(_round1(), [])
    headlines = [c.headline for c in clusters]
    # The four Trade Desk phrasings should land in a single cluster.
    trade_desk_clusters = [c for c in clusters if "trade desk" in c.headline.lower()]
    assert len(trade_desk_clusters) == 1
    td = trade_desk_clusters[0]
    assert sorted(td.support_models) == ["claude", "deepseek", "gpt"]
    assert td.support_count == 3
    assert td.severity == "high"  # 3+ models → high severity
    # Headline should be the longest representative.
    assert len(td.headline) > 50
    # Each unique phrasing is preserved as a member — 3 key_risks + 1 hidden
    # assumption all reference Trade Desk and merge into one cluster.
    assert len(td.members) == 4


def test_total_cluster_count_collapses_the_panel():
    clusters = cluster_risks(_round1(), [])
    # 8 raw risks across 4 models — should collapse to ~5 clusters (trade desk
    # group + 4 distinct single-model risks). Must be <= 8 raw bullets and
    # comfortably under the plan's "≤ 8 clusters" success criterion.
    assert len(clusters) <= 8
    assert len(clusters) < 8  # paraphrases collapsed


def test_cluster_headlines_backcompat():
    clusters = cluster_risks(_round1(), [])
    legacy = cluster_headlines(clusters)
    # Legacy hidden_risks shape preserved: list[str].
    assert all(isinstance(s, str) for s in legacy)
    assert len(legacy) == len(clusters)


def test_invalidator_promotes_severity():
    round1 = {
        "gpt": IndependentOpinion(
            model="gpt",
            stance="bullish",
            confidence=0.7,
            key_risks=[],
            invalidators=["Fed surprise hike of 50bp would invalidate this view"],
        ),
    }
    clusters = cluster_risks(round1, [])
    assert len(clusters) == 1
    # 1 model but invalidator-sourced → high severity.
    assert clusters[0].severity == "high"


def test_clustering_is_deterministic():
    r = _round1()
    a = [c.to_dict() for c in cluster_risks(r, [])]
    b = [c.to_dict() for c in cluster_risks(r, [])]
    assert a == b


def test_debate_round_risks_are_included():
    round1 = {
        "gpt": IndependentOpinion(
            model="gpt",
            stance="bullish",
            confidence=0.7,
            key_risks=["Trade Desk warning on digital advertising spend"],
        ),
    }
    debate = [
        {
            "claude": DebateCritique(
                model="claude",
                new_risks_identified=["Trade Desk caution signals ad market weakness"],
            ),
        },
    ]
    clusters = cluster_risks(round1, debate)
    # Both risks share the "trade desk" domain entity → must cluster together
    # regardless of round of origin.
    assert any({"gpt", "claude"}.issubset(set(c.support_models)) for c in clusters)
