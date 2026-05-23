"""Equal-weight stance aggregation and calibration utilities.

Design notes
------------
- ``mixed`` is treated as a non-directional stance (score = 0.0). Previously it
  was scored as +0.25, which silently biased the mean toward bullish even when
  most models reported uncertainty. ``mixed`` and ``neutral`` aggregate
  identically; they remain distinct *labels* for display purposes.
- Consensus is computed deterministically via two parallel mechanisms:
    1. Mean-stance label (continuous, fine-grained, threshold-bucketed)
    2. Stance plurality (discrete, transparent, majority-respecting)
  A reconciled label combines them — favouring plurality when it is decisive
  or non-directional, falling back to the mean-stance label otherwise.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import TypedDict

from app.services.deliberation.schemas import IndependentOpinion, Stance

STANCE_SCORES: dict[Stance, float] = {
    "bullish": 1.0,
    "bearish": -1.0,
    "neutral": 0.0,
    "mixed": 0.0,
}

DIRECTIONAL_STANCES: set[str] = {"bullish", "bearish"}
NON_DIRECTIONAL_STANCES: set[str] = {"mixed", "neutral"}


def stance_to_score(stance: str) -> float:
    return STANCE_SCORES.get(stance.lower(), 0.0)  # type: ignore[arg-type]


def score_to_consensus_label(mean_score: float) -> str:
    if mean_score >= 0.65:
        return "strong bullish"
    if mean_score >= 0.35:
        return "bullish"
    if mean_score >= 0.15:
        return "weak bullish"
    if mean_score <= -0.65:
        return "strong bearish"
    if mean_score <= -0.35:
        return "bearish"
    if mean_score <= -0.15:
        return "weak bearish"
    if abs(mean_score) < 0.08:
        return "neutral"
    return "mixed"


def equal_weight_mean_stance(opinions: list[IndependentOpinion]) -> tuple[float, str]:
    valid = [o for o in opinions if not o.error]
    if not valid:
        return 0.0, "neutral"
    scores = [stance_to_score(o.stance) for o in valid]
    mean = sum(scores) / len(scores)
    return mean, score_to_consensus_label(mean)


def agreement_score(opinions: list[IndependentOpinion]) -> float:
    valid = [o for o in opinions if not o.error]
    if len(valid) < 2:
        return 1.0
    scores = [stance_to_score(o.stance) for o in valid]
    mean = sum(scores) / len(scores)
    variance = sum((s - mean) ** 2 for s in scores) / len(scores)
    return round(max(0.0, 1.0 - variance), 3)


def stance_plurality(opinions: list[IndependentOpinion]) -> tuple[str, int, int]:
    """Return ``(plurality_stance, count, total_valid)``.

    Ties are broken by a stable preference order (mixed > neutral > bullish >
    bearish) — non-directional labels win ties so the reconciled verdict does
    not silently take a directional side without a real majority.
    """
    valid = [o for o in opinions if not o.error]
    total = len(valid)
    if total == 0:
        return "neutral", 0, 0
    counts = Counter(o.stance for o in valid)
    preference = ["mixed", "neutral", "bullish", "bearish"]
    best_stance = max(
        counts.items(),
        key=lambda kv: (kv[1], -preference.index(kv[0]) if kv[0] in preference else -99),
    )
    return best_stance[0], best_stance[1], total


def support_counts(opinions: list[IndependentOpinion]) -> dict[str, list[str]]:
    """Map each observed stance to the list of model ids that hold it."""
    out: dict[str, list[str]] = {}
    for op in opinions:
        if op.error:
            continue
        out.setdefault(op.stance, []).append(op.model)
    return out


def stance_entropy(opinions: list[IndependentOpinion]) -> float:
    """Shannon entropy over stance distribution, normalized to [0, 1]."""
    valid = [o for o in opinions if not o.error]
    if not valid:
        return 0.0
    counts = Counter(o.stance for o in valid)
    total = len(valid)
    probs = [c / total for c in counts.values()]
    if len(probs) < 2:
        return 0.0
    h = -sum(p * math.log(p, 2) for p in probs if p > 0)
    max_h = math.log(min(len(STANCE_SCORES), total), 2)
    return h / max_h if max_h > 0 else 0.0


def reconcile_verdict_label(
    opinions: list[IndependentOpinion],
    mean_label: str,
) -> str:
    """Combine plurality and mean-score signals into a single honest label.

    Rules:
    - If the plurality stance is non-directional (``mixed``/``neutral``) and
      it covers >= ceil(n/2) models, use the plurality label outright.
    - If the plurality is non-directional but smaller, blend: e.g.
      ``mixed_with_bullish_tilt`` when the mean leans bullish.
    - If the plurality is directional and majoritarian, use that direction.
    - Otherwise fall back to the mean-score label.
    """
    plurality, count, total = stance_plurality(opinions)
    if total == 0:
        return mean_label

    majority_threshold = (total + 1) // 2

    if plurality in NON_DIRECTIONAL_STANCES:
        if count >= majority_threshold:
            return plurality
        if "bullish" in mean_label:
            return f"{plurality}_with_bullish_tilt"
        if "bearish" in mean_label:
            return f"{plurality}_with_bearish_tilt"
        return plurality

    if count >= majority_threshold:
        return mean_label
    return mean_label


class CalibrationBlock(TypedDict):
    directional_conviction: float
    consensus_strength: float
    evidence_quality: float
    confidence_aggregate: float
    uncertainty: str


def compute_calibration(
    opinions: list[IndependentOpinion],
    *,
    divergence: float,
    reasoning_overlap: float,
    contradiction_density: float,
    confidence_spread: float,
    agreement: float,
) -> CalibrationBlock:
    """Build the calibration dictionary attached to every ConsensusOutput.

    - ``directional_conviction`` = |mean_score| — how strongly the centroid
      leans in any direction. 0 means a perfectly balanced or non-directional
      panel.
    - ``consensus_strength`` = ``1 - stance_entropy`` — independent of
      direction; 1.0 means all models picked the same label.
    - ``evidence_quality`` = blend of reasoning overlap and confidence
      stability — penalised by wide confidence spreads.
    - ``confidence_aggregate`` = mean model confidence dampened by ``(1 -
      0.5 * divergence)``. This is the published consensus confidence; it can
      never exceed the average model confidence.
    - ``uncertainty`` mirrors the existing rule but is now computed from the
      calibration block itself.
    """
    valid = [o for o in opinions if not o.error]
    if not valid:
        return CalibrationBlock(
            directional_conviction=0.0,
            consensus_strength=0.0,
            evidence_quality=0.0,
            confidence_aggregate=0.0,
            uncertainty="high",
        )

    scores = [stance_to_score(o.stance) for o in valid]
    mean = sum(scores) / len(scores)
    directional_conviction = round(min(1.0, abs(mean)), 3)

    consensus_strength = round(max(0.0, 1.0 - stance_entropy(valid)), 3)

    overlap = max(0.0, min(1.0, reasoning_overlap))
    spread_penalty = max(0.0, min(1.0, confidence_spread))
    evidence_quality = round(max(0.0, min(1.0, 0.6 * overlap + 0.4 * (1.0 - spread_penalty))), 3)

    mean_conf = sum(o.confidence for o in valid) / len(valid)
    damping = max(0.0, 1.0 - 0.5 * max(0.0, min(1.0, divergence)))
    confidence_aggregate = round(max(0.0, min(1.0, mean_conf * damping)), 3)

    if (
        agreement < 0.45
        or contradiction_density > 0.5
        or spread_penalty > 0.35
        or consensus_strength < 0.3
    ):
        uncertainty = "high"
    elif (
        agreement < 0.7
        or contradiction_density > 0.25
        or spread_penalty > 0.2
        or consensus_strength < 0.6
    ):
        uncertainty = "medium"
    else:
        uncertainty = "low"

    return CalibrationBlock(
        directional_conviction=directional_conviction,
        consensus_strength=consensus_strength,
        evidence_quality=evidence_quality,
        confidence_aggregate=confidence_aggregate,
        uncertainty=uncertainty,
    )
