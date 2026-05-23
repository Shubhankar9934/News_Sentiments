"""Unit tests for deterministic deliberation scoring."""

from app.services.deliberation.debate.consensus import synthesize_consensus
from app.services.deliberation.schemas import (
    DebateCritique,
    IndependentOpinion,
    ReasoningStep,
)
from app.services.deliberation.scoring.disagreement import build_metrics
from app.services.deliberation.scoring.weighting import (
    agreement_score,
    compute_calibration,
    equal_weight_mean_stance,
    reconcile_verdict_label,
    score_to_consensus_label,
    stance_plurality,
    stance_to_score,
    support_counts,
)


def test_stance_scoring():
    assert stance_to_score("bullish") == 1.0
    assert stance_to_score("bearish") == -1.0
    assert stance_to_score("mixed") == 0.0  # PR1: was 0.25
    assert stance_to_score("neutral") == 0.0
    assert score_to_consensus_label(0.5) == "bullish"


def test_agreement_score_uniform():
    ops = [
        IndependentOpinion(model="gpt", stance="bullish", confidence=0.7),
        IndependentOpinion(model="claude", stance="bullish", confidence=0.8),
    ]
    assert agreement_score(ops) == 1.0


def test_agreement_score_split():
    ops = [
        IndependentOpinion(model="gpt", stance="bullish", confidence=0.7),
        IndependentOpinion(model="claude", stance="bearish", confidence=0.6),
    ]
    assert agreement_score(ops) < 0.6


def test_disagreement_matrix():
    round1 = {
        "gpt": IndependentOpinion(
            model="gpt",
            stance="bullish",
            confidence=0.7,
            reasoning_steps=[
                ReasoningStep(step=1, title="Macro Analysis", analysis="Fed pivot supports risk-on")
            ],
        ),
        "claude": IndependentOpinion(
            model="claude",
            stance="bearish",
            confidence=0.6,
            reasoning_steps=[
                ReasoningStep(step=1, title="Valuation concerns", analysis="Multiple compression risk")
            ],
        ),
    }
    metrics = build_metrics(round1, [])
    assert "macro" in metrics.disagreement_matrix
    assert metrics.model_divergence > 0


def test_consensus_synthesis():
    round1 = {
        "gpt": IndependentOpinion(model="gpt", stance="bullish", confidence=0.7, key_risks=["rates"]),
        "claude": IndependentOpinion(
            model="claude", stance="bullish", confidence=0.65, key_risks=["liquidity"]
        ),
    }
    debate = [
        {
            "gpt": DebateCritique(
                model="gpt",
                confidence_revision=None,
                new_risks_identified=["earnings miss"],
            )
        }
    ]
    parsed = {k: DebateCritique.model_validate(v) for k, v in debate[0].items()}
    metrics = build_metrics(round1, [parsed])
    consensus = synthesize_consensus(round1, [parsed], metrics)
    assert consensus.consensus
    assert 0 <= consensus.agreement_score <= 1
    assert consensus.uncertainty in ("high", "medium", "low")
    assert len(consensus.hidden_risks) >= 1


def _failing_example_round1():
    """Reproduces the canonical failing case from the audit:
    {GPT: mixed, Groq: bullish, Claude: neutral, DeepSeek: mixed} with
    individual confidences ~ 0.60 / 0.65 / 0.52 / 0.55.
    """
    return {
        "gpt": IndependentOpinion(model="gpt", stance="mixed", confidence=0.60),
        "groq": IndependentOpinion(model="groq", stance="bullish", confidence=0.65),
        "claude": IndependentOpinion(model="claude", stance="neutral", confidence=0.52),
        "deepseek": IndependentOpinion(model="deepseek", stance="mixed", confidence=0.55),
    }


def test_mixed_neutral_no_longer_inflate_to_bullish():
    """PR1 fix: a panel of {mixed, bullish, neutral, mixed} must not produce
    a 'bullish' verdict via mean-score threshold. With mixed=0.0 the mean
    drops to 0.25 (was 0.375) and the label becomes 'weak bullish'; the
    reconciled label must surface the non-directional plurality."""
    round1 = _failing_example_round1()
    opinions = list(round1.values())
    mean, label = equal_weight_mean_stance(opinions)
    assert mean == 0.25  # (0 + 1 + 0 + 0) / 4 — was 0.375 before PR1
    assert label != "bullish"  # no longer crosses the 0.35 threshold


def test_stance_plurality_picks_non_directional_majority():
    round1 = _failing_example_round1()
    plurality, count, total = stance_plurality(list(round1.values()))
    assert plurality == "mixed"
    assert count == 2
    assert total == 4


def test_reconcile_verdict_label_for_failing_example():
    round1 = _failing_example_round1()
    opinions = list(round1.values())
    _, mean_label = equal_weight_mean_stance(opinions)
    reconciled = reconcile_verdict_label(opinions, mean_label)
    assert reconciled in ("mixed", "mixed_with_bullish_tilt")


def test_support_counts_for_failing_example():
    round1 = _failing_example_round1()
    counts = support_counts(list(round1.values()))
    assert counts == {
        "mixed": ["gpt", "deepseek"],
        "bullish": ["groq"],
        "neutral": ["claude"],
    }


def test_calibration_block_no_confidence_inflation():
    """PR1 success criterion: confidence_aggregate must not exceed the mean
    of individual confidences. For the failing example (avg ~0.58), the
    published consensus confidence must stay <= 0.62."""
    round1 = _failing_example_round1()
    metrics = build_metrics(round1, [])
    cal = compute_calibration(
        list(round1.values()),
        divergence=metrics.model_divergence,
        reasoning_overlap=metrics.reasoning_overlap,
        contradiction_density=metrics.contradiction_density,
        confidence_spread=metrics.confidence_spread,
        agreement=metrics.model_divergence,
    )
    assert cal["directional_conviction"] <= 0.40
    assert cal["confidence_aggregate"] <= 0.62
    # mean stance is 0.25 — directional conviction is exactly that
    assert cal["directional_conviction"] == 0.25


def test_consensus_synthesis_attaches_calibration_for_failing_example():
    round1 = _failing_example_round1()
    metrics = build_metrics(round1, [])
    consensus = synthesize_consensus(round1, [], metrics)
    assert consensus.calibration is not None
    assert consensus.reconciled_label in ("mixed", "mixed_with_bullish_tilt")
    assert consensus.support_counts["mixed"] == ["gpt", "deepseek"]
    # Legacy fields must remain populated for back-compat:
    assert consensus.consensus  # mean-score label
    assert consensus.dominant_thesis.startswith("mixed (")


def test_context_builder():
    from app.services.deliberation.context_builder import build_deliberation_context

    report = {
        "overall_sentiment_score": 0.3,
        "overall_sentiment_label": "Bullish",
        "key_events": [{"type": "earnings", "description": "beat"}],
        "price_prediction": {"bias": "Bullish"},
        "_pipeline_meta": {
            "volatility_regime": "medium",
            "article_evidence": [{"headline": "Test"}],
        },
    }
    ctx = build_deliberation_context(report, "AAPL")
    assert ctx.ticker == "AAPL"
    assert ctx.key_events[0]["type"] == "earnings"
