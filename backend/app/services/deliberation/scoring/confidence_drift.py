"""Confidence drift before/after debate."""

from __future__ import annotations

from typing import Any

from app.services.deliberation.schemas import DebateCritique, IndependentOpinion, ModelKey


def compute_confidence_drift(
    round1: dict[str, IndependentOpinion],
    debate_rounds: list[dict[str, DebateCritique]],
) -> list[dict[str, Any]]:
    final_by_model: dict[ModelKey, float] = {}
    for rd in reversed(debate_rounds):
        for key, critique in rd.items():
            if critique.confidence_revision and key not in final_by_model:
                final_by_model[key] = critique.confidence_revision.new

    drift: list[dict[str, Any]] = []
    for model, opinion in round1.items():
        if opinion.error:
            continue
        before = opinion.confidence
        after = final_by_model.get(model, before)
        drift.append(
            {
                "model": model,
                "before": round(before, 3),
                "after": round(after, 3),
                "delta": round(after - before, 3),
            }
        )
    return drift
