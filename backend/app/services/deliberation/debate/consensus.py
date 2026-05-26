"""Deterministic consensus synthesis — no LLM arbiter."""

from __future__ import annotations

from app.core.config import settings as global_settings
from app.services.deliberation.schemas import (
    CalibrationOutput,
    ConsensusOutput,
    DebateCritique,
    DeliberationMetrics,
    IndependentOpinion,
)
from app.services.deliberation.scoring.disagreement import main_conflicts
from app.services.deliberation.scoring.risk_clustering import (
    cluster_headlines,
    cluster_risks,
)
from app.services.deliberation.scoring.thesis_clustering import build_thesis_clusters
from app.services.deliberation.scoring.weighting import (
    agreement_score,
    compute_calibration,
    equal_weight_mean_stance,
    reconcile_verdict_label,
    score_to_consensus_label,
    stance_to_score,
    support_counts,
)


def _collect_hidden_risks(
    round1: dict[str, IndependentOpinion],
    debate_rounds: list[dict[str, DebateCritique]],
) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for op in round1.values():
        for r in op.key_risks + op.hidden_assumptions:
            k = r.strip().lower()
            if k and k not in seen:
                seen.add(k)
                out.append(r)
    for rd in debate_rounds:
        for c in rd.values():
            for r in c.new_risks_identified:
                k = r.strip().lower()
                if k and k not in seen:
                    seen.add(k)
                    out.append(r)
    return out[:25]


def _uncertainty_level(
    agreement: float,
    metrics: DeliberationMetrics,
    opinions: list[IndependentOpinion],
) -> str:
    spread = metrics.confidence_spread
    density = metrics.contradiction_density
    if agreement < 0.45 or density > 0.5 or spread > 0.35:
        return "high"
    if agreement < 0.7 or density > 0.25 or spread > 0.2:
        return "medium"
    return "low"


def _recommended_positioning(consensus_label: str, risks: list[str]) -> str:
    risk_n = len(risks)
    label_lc = consensus_label.lower()
    if "strong bearish" in label_lc or label_lc == "bearish":
        base = "Defensive / reduce exposure; favor hedges."
    elif "strong bullish" in label_lc or label_lc == "bullish":
        base = "Moderate long bias; scale in with defined risk limits."
    elif "weak bullish" in label_lc or "bullish_tilt" in label_lc:
        base = "Small tactical long or wait for confirmation."
    elif "weak bearish" in label_lc or "bearish_tilt" in label_lc:
        base = "Underweight / tight stops; avoid aggressive adds."
    else:
        base = "Neutral / range-trade; wait for narrative clarity."
    if risk_n >= 8:
        return f"{base} Elevated hidden-risk count — size down."
    if risk_n >= 4:
        return f"{base} Monitor disagreement-driven risks."
    return base


def _dominant_and_conflicting_theses(round1: dict[str, IndependentOpinion]) -> tuple[str, str]:
    by_stance: dict[str, list[str]] = {}
    for desk_key, op in round1.items():
        if op.error:
            continue
        label = op.role_label or desk_key
        by_stance.setdefault(op.stance, []).append(label)
    if not by_stance:
        return "", ""
    dominant_stance = max(by_stance.keys(), key=lambda s: len(by_stance[s]))
    dominant = f"{dominant_stance} ({', '.join(by_stance[dominant_stance])})"
    others = [s for s in by_stance if s != dominant_stance]
    conflicting = "; ".join(f"{s}: {', '.join(by_stance[s])}" for s in others) if others else ""
    return dominant, conflicting


def synthesize_consensus(
    round1: dict[str, IndependentOpinion],
    debate_rounds: list[dict[str, DebateCritique]],
    metrics: DeliberationMetrics,
) -> ConsensusOutput:
    opinions = list(round1.values())
    mean_score, label = equal_weight_mean_stance(opinions)
    agree = agreement_score(opinions)

    structured_risks: list[dict] = []
    if global_settings.dil_use_risk_clustering:
        clusters = cluster_risks(round1, debate_rounds)
        structured_risks = [c.to_dict() for c in clusters]
        hidden = cluster_headlines(clusters)
        # Fallback when clustering yields nothing usable (e.g. empty inputs):
        # keep the legacy flat list so the UI never sees an empty section.
        if not hidden:
            hidden = _collect_hidden_risks(round1, debate_rounds)
    else:
        hidden = _collect_hidden_risks(round1, debate_rounds)
    uncertainty = _uncertainty_level(agree, metrics, opinions)
    dominant, conflicting = _dominant_and_conflicting_theses(round1)
    conflicts = main_conflicts(metrics.disagreement_matrix)

    reconciled = reconcile_verdict_label(opinions, label)
    counts = support_counts(opinions)
    calibration_dict = compute_calibration(
        opinions,
        divergence=metrics.model_divergence,
        reasoning_overlap=metrics.reasoning_overlap,
        contradiction_density=metrics.contradiction_density,
        confidence_spread=metrics.confidence_spread,
        agreement=agree,
    )
    calibration = CalibrationOutput(**calibration_dict)

    desks_n = len([o for o in opinions if not o.error])
    debate_summary = (
        f"{desks_n} desks deliberated across {len(debate_rounds)} debate rounds. "
        f"Agreement {agree:.0%}, directional conviction "
        f"{calibration.directional_conviction:.0%}, consensus strength "
        f"{calibration.consensus_strength:.0%}, divergence "
        f"{metrics.model_divergence:.2f}, contradiction density "
        f"{metrics.contradiction_density:.2f}. "
        f"Disagreement is treated as signal, not noise."
    )

    thesis_clusters = [c.to_dict() for c in build_thesis_clusters(round1)]

    return ConsensusOutput(
        consensus=label,
        agreement_score=agree,
        uncertainty=uncertainty,  # type: ignore[arg-type]
        main_conflicts=conflicts[:10],
        hidden_risks=hidden,
        recommended_positioning=_recommended_positioning(reconciled, hidden),
        debate_summary=debate_summary,
        dominant_thesis=dominant,
        conflicting_thesis=conflicting,
        reconciled_label=reconciled,
        support_counts=counts,
        calibration=calibration,
        structured_risks=structured_risks,
        thesis_clusters=thesis_clusters,
    )
