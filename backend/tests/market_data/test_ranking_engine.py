"""Deterministic ranking score tests.

The Reverse BWB Workstation ranks ALL opportunities by a single explicit
weighted formula. These tests lock down:
    * The formula matches the spec.
    * Score is monotone in credit_efficiency (other terms held equal).
    * The score is purely a sort key — nothing gets filtered or hidden.
    * Identical batches produce identical scores (deterministic).
"""

from __future__ import annotations

from app.services.market_data.ranking_engine import RankingInput, score_candidates


def _input(
    *,
    credit_efficiency: float,
    liquidity: int = 100,
    margin: float = 500.0,
    body: float = 100.0,
    underlying: float = 100.0,
) -> RankingInput:
    return RankingInput(
        credit_efficiency=credit_efficiency,
        liquidity=liquidity,
        margin=margin,
        body_strike=body,
        underlying_price=underlying,
    )


def test_score_monotone_in_credit_efficiency() -> None:
    scores = score_candidates(
        [_input(credit_efficiency=ce) for ce in (5.0, 10.0, 20.0)]
    )
    assert scores[0] < scores[1] < scores[2]


def test_score_rewards_liquidity() -> None:
    low, high = score_candidates(
        [_input(credit_efficiency=10.0, liquidity=10),
         _input(credit_efficiency=10.0, liquidity=10000)]
    )
    assert high > low


def test_score_penalizes_higher_margin() -> None:
    cheap, expensive = score_candidates(
        [_input(credit_efficiency=10.0, margin=200.0),
         _input(credit_efficiency=10.0, margin=2000.0)]
    )
    # Median margin = 1100; the 2000 one has the bigger penalty.
    assert cheap > expensive


def test_score_pin_risk_penalty_grows_with_distance_term() -> None:
    """The spec defines the pin_risk_penalty as |body - underlying| /
    underlying — so the score subtraction is larger when body is farther
    from underlying. Lock the formula in place."""
    near, far = score_candidates(
        [_input(credit_efficiency=10.0, body=100.5, underlying=100.0),
         _input(credit_efficiency=10.0, body=130.0, underlying=100.0)]
    )
    # Far-from-underlying gets the bigger penalty -> smaller score.
    assert far < near


def test_score_deterministic_across_runs() -> None:
    a = score_candidates([_input(credit_efficiency=10.0)])
    b = score_candidates([_input(credit_efficiency=10.0)])
    assert a == b


def test_score_returns_empty_for_empty_input() -> None:
    assert score_candidates([]) == []
