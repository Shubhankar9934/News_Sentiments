"""Round-novelty scoring for debate revisions.

Round 2 (revision) previously received only the model's own prior critique as
context, which produced near-verbatim restatements: same
``strongest_counterargument``, same ``weakest_reasoning_detected``, same
``new_risks_identified``. This module computes the textual overlap between a
revision and the prior critique so we can flag low-novelty responses.

Token-set Jaccard is deliberately deterministic and cheap — no embeddings or
LLM calls. Models flagged ``low_novelty=true`` are surfaced in the UI; an
optional re-prompt loop (off by default for cost) can be added downstream.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.deliberation.schemas import DebateCritique

_WORD_RE = re.compile(r"[a-z]{4,}")


@dataclass
class NoveltyScore:
    model: str
    similarity: float
    low_novelty: bool

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "similarity": round(self.similarity, 3),
            "low_novelty": self.low_novelty,
        }


def _token_set(*texts: str) -> set[str]:
    tokens: set[str] = set()
    for t in texts:
        if not t:
            continue
        for w in _WORD_RE.findall(t.lower()):
            tokens.add(w)
    return tokens


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def critique_signature(critique: DebateCritique) -> set[str]:
    """Build the token-set used for similarity comparisons.

    We blend the freeform fields most likely to be restated verbatim:
    ``strongest_counterargument``, ``weakest_reasoning_detected``, and the
    list of newly identified risks.
    """
    return _token_set(
        critique.strongest_counterargument or "",
        critique.weakest_reasoning_detected or "",
        " ".join(critique.new_risks_identified or []),
    )


def score_round_novelty(
    prior_round: dict[str, DebateCritique],
    revision_round: dict[str, DebateCritique],
    *,
    threshold: float = 0.7,
) -> list[NoveltyScore]:
    """Compare each model's revision against its own prior critique.

    A revision whose Jaccard similarity to the prior critique exceeds the
    threshold is flagged as ``low_novelty=True``. Models that errored in
    either round are skipped.
    """
    scores: list[NoveltyScore] = []
    for model, revision in revision_round.items():
        prior = prior_round.get(model)
        if revision.error or prior is None or prior.error:
            continue
        sim = _jaccard(critique_signature(prior), critique_signature(revision))
        scores.append(
            NoveltyScore(
                model=model,
                similarity=sim,
                low_novelty=sim > threshold,
            )
        )
    return scores
