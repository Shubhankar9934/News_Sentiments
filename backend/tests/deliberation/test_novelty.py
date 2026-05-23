"""Tests for round-novelty scoring."""

from __future__ import annotations

from app.services.deliberation.schemas import DebateCritique
from app.services.deliberation.scoring.novelty import (
    critique_signature,
    score_round_novelty,
)


def _critique(model: str, counter: str, weak: str, risks: list[str]) -> DebateCritique:
    return DebateCritique(
        model=model,
        strongest_counterargument=counter,
        weakest_reasoning_detected=weak,
        new_risks_identified=risks,
    )


def test_identical_revision_flagged_low_novelty():
    prior = {
        "gpt": _critique(
            "gpt",
            "Groq overweights Nvidia earnings impact on Alphabet ad revenue",
            "Position size suggestion is overly confident given mixed macro",
            ["Trade Desk warning hurts ad revenue"],
        ),
    }
    revision = {
        "gpt": _critique(
            "gpt",
            "Groq overweights Nvidia earnings impact on Alphabet ad revenue",
            "Position size suggestion is overly confident given mixed macro",
            ["Trade Desk warning hurts ad revenue"],
        ),
    }
    scores = score_round_novelty(prior, revision, threshold=0.7)
    assert len(scores) == 1
    assert scores[0].model == "gpt"
    assert scores[0].similarity == 1.0
    assert scores[0].low_novelty is True


def test_genuinely_new_revision_not_flagged():
    prior = {
        "gpt": _critique(
            "gpt",
            "Groq overweights Nvidia earnings impact",
            "Position size suggestion overly confident",
            ["Trade Desk warning"],
        ),
    }
    revision = {
        "gpt": _critique(
            "gpt",
            "Conceding Groq on macro tailwind but maintain stance on ad revenue exposure given Waymo regulatory overhang",
            "Underweighted rotation risk away from megacap names per recent flow data",
            ["Rotation pressure toward smaller AI beneficiaries"],
        ),
    }
    scores = score_round_novelty(prior, revision, threshold=0.7)
    assert scores[0].low_novelty is False
    assert scores[0].similarity < 0.5


def test_errored_models_skipped():
    prior = {
        "gpt": DebateCritique(model="gpt", error="boom"),
        "claude": _critique("claude", "x y z", "a b c", ["risk one"]),
    }
    revision = {
        "gpt": _critique("gpt", "x y z", "a b c", ["risk one"]),
        "claude": _critique("claude", "x y z", "a b c", ["risk one"]),
    }
    scores = score_round_novelty(prior, revision)
    models = {s.model for s in scores}
    assert models == {"claude"}  # gpt prior errored — skipped


def test_signature_uses_4plus_letter_tokens():
    c = _critique("gpt", "AI go!", "a", [])
    # "AI" (2 letters) and "go" (2 letters) are below the 4-letter floor; only
    # words of length >= 4 contribute to the signature.
    assert critique_signature(c) == set()
