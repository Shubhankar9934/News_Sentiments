"""Tests for quorum evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.dil_resilience.quorum import QuorumEvaluator


@dataclass
class _Member:
    error: str | None = None


def test_meets_quorum_not_degraded() -> None:
    round1 = {
        "a": _Member(),
        "b": _Member(),
        "c": _Member(),
    }
    result = QuorumEvaluator.evaluate(round1, required=2, total=3)
    assert result.meets_quorum
    assert not result.degraded
    assert result.valid_count == 3


def test_meets_quorum_degraded() -> None:
    round1 = {
        "a": _Member(),
        "b": _Member(),
        "c": _Member(error="failed"),
    }
    result = QuorumEvaluator.evaluate(round1, required=2, total=3)
    assert result.meets_quorum
    assert result.degraded
    assert result.valid_count == 2


def test_below_quorum() -> None:
    round1 = {
        "a": _Member(error="x"),
        "b": _Member(error="y"),
        "c": _Member(),
    }
    result = QuorumEvaluator.evaluate(round1, required=2, total=3)
    assert not result.meets_quorum
    assert not result.degraded
