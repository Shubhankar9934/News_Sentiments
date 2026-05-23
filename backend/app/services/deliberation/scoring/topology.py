"""Disagreement Topology — treat divergence as a first-class signal.

The legacy DIL exposed only a single ``disagreement_matrix`` (topic × model
stance) plus a few scalar metrics. That is enough to *show* disagreement but
not to *map* it. Institutional decision support needs to know **where** the
panel refuses to converge: directionally, on confidence, on which evidence
each model is leaning on, on which risks they think matter, and on what
time horizon they care about.

This module computes five disagreement axes — each scored in ``[0, 1]`` so
they can be plotted as a radar chart or rolled into a single divergence
fingerprint:

- ``directional`` — variance of numeric stance scores.
- ``confidence`` — std-dev of model confidences.
- ``evidence``   — Jaccard distance over entity tokens cited in reasoning.
- ``risk``       — Jaccard distance over clustered risk membership.
- ``timing``     — variance over ordinal-mapped time horizons.

``hot_topics`` highlights which topics in the disagreement matrix flipped to
``oppose`` — those are the rows decision-makers should focus on.
"""

from __future__ import annotations

import re
from typing import Iterable

from app.services.deliberation.schemas import IndependentOpinion
from app.services.deliberation.scoring.risk_clustering import RiskCluster
from app.services.deliberation.scoring.weighting import stance_to_score

_TIMING_ORDINALS: dict[str, int] = {
    "intraday": 0,
    "0-1d": 0,
    "1d": 1,
    "1-3d": 2,
    "3d": 2,
    "1w": 3,
    "1-2w": 4,
    "2w": 4,
    "1m": 6,
    "1-3m": 7,
    "3m": 8,
    "3-6m": 9,
    "6m": 10,
    "1y": 12,
}

_WORD_RE = re.compile(r"[a-z][a-z\-']{3,}")
_STOPWORDS: set[str] = {
    "with", "from", "that", "this", "have", "will", "could", "would", "should",
    "their", "there", "these", "those", "into", "onto", "than", "then", "very",
    "more", "less", "much", "some", "many", "most", "least", "about", "such",
    "what", "when", "where", "which", "while", "still", "been", "being",
    "above", "below", "near", "also", "even", "just", "only", "very",
}


def _ordinal_for_horizon(h: str) -> int | None:
    if not h:
        return None
    key = h.strip().lower().replace(" ", "")
    return _TIMING_ORDINALS.get(key)


def _evidence_tokens(op: IndependentOpinion) -> set[str]:
    tokens: set[str] = set()
    for step in op.reasoning_steps:
        for w in _WORD_RE.findall(step.analysis.lower()):
            if w not in _STOPWORDS:
                tokens.add(w)
    return tokens


def _jaccard_distance(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return 1.0 - len(a & b) / len(union)


def _mean_pairwise(values: Iterable[float]) -> float:
    vals = list(values)
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


def _pairwise(items: list) -> list[tuple]:
    out: list[tuple] = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            out.append((items[i], items[j]))
    return out


def _directional_axis(opinions: list[IndependentOpinion]) -> float:
    scores = [stance_to_score(o.stance) for o in opinions if not o.error]
    if len(scores) < 2:
        return 0.0
    mean = sum(scores) / len(scores)
    variance = sum((s - mean) ** 2 for s in scores) / len(scores)
    # Variance of values in [-1, 1] is bounded by 1.0 — use it directly.
    return round(min(1.0, variance), 3)


def _confidence_axis(opinions: list[IndependentOpinion]) -> float:
    confs = [o.confidence for o in opinions if not o.error]
    if len(confs) < 2:
        return 0.0
    mean = sum(confs) / len(confs)
    variance = sum((c - mean) ** 2 for c in confs) / len(confs)
    # Std-dev of values in [0, 1] is bounded by 0.5; scale to [0, 1].
    return round(min(1.0, (variance ** 0.5) / 0.5), 3)


def _evidence_axis(opinions: list[IndependentOpinion]) -> float:
    token_sets = [_evidence_tokens(o) for o in opinions if not o.error]
    if len(token_sets) < 2:
        return 0.0
    distances = [_jaccard_distance(a, b) for a, b in _pairwise(token_sets)]
    return round(_mean_pairwise(distances), 3)


def _risk_axis(
    opinions: list[IndependentOpinion],
    clusters: list[RiskCluster],
) -> float:
    if not clusters:
        return 0.0
    valid_models = [o.model for o in opinions if not o.error]
    if len(valid_models) < 2:
        return 0.0
    by_model: dict[str, set[str]] = {m: set() for m in valid_models}
    for c in clusters:
        for m in c.support_models:
            if m in by_model:
                by_model[m].add(c.cluster_id)
    sets = [by_model[m] for m in valid_models]
    distances = [_jaccard_distance(a, b) for a, b in _pairwise(sets)]
    return round(_mean_pairwise(distances), 3)


def _timing_axis(opinions: list[IndependentOpinion]) -> float:
    ordinals: list[int] = []
    for o in opinions:
        if o.error:
            continue
        ord_v = _ordinal_for_horizon(o.time_horizon)
        if ord_v is not None:
            ordinals.append(ord_v)
    if len(ordinals) < 2:
        return 0.0
    mean = sum(ordinals) / len(ordinals)
    spread = (sum((x - mean) ** 2 for x in ordinals) / len(ordinals)) ** 0.5
    # Largest credible horizon is ~12; normalize by half of that.
    return round(min(1.0, spread / 6.0), 3)


def _hot_topics(disagreement_matrix: dict[str, dict[str, str]]) -> list[str]:
    return [
        topic
        for topic, row in disagreement_matrix.items()
        if not topic.startswith("_") and row.get("_alignment") == "oppose"
    ]


def build_disagreement_topology(
    round1: dict[str, IndependentOpinion],
    disagreement_matrix: dict[str, dict[str, str]],
    clusters: list[RiskCluster],
) -> dict:
    opinions = list(round1.values())
    axes = {
        "directional": _directional_axis(opinions),
        "confidence": _confidence_axis(opinions),
        "evidence": _evidence_axis(opinions),
        "risk": _risk_axis(opinions, clusters),
        "timing": _timing_axis(opinions),
    }
    total = sum(axes.values())
    overall = round(min(1.0, total / 5.0), 3)
    return {
        "axes": axes,
        "overall": overall,
        "hot_topics": _hot_topics(disagreement_matrix),
    }


def detect_contradictions(
    round1: dict[str, IndependentOpinion],
    disagreement_matrix: dict[str, dict[str, str]],
    clusters: list[RiskCluster],
    reasoning_overlap: float,
) -> list[dict]:
    """Surface concrete contradictions across three families:

    - ``pair_topic`` — two models hold opposing directional stances on the
      same topic (e.g. macro: bullish vs bearish).
    - ``stance_vs_evidence`` — a model's headline stance is directional but
      the clustered risks it surfaced lean the *other* way.
    - ``confidence_vs_reasoning`` — a model reports high confidence while
      panel-wide reasoning overlap is low (rare evidence is supporting a
      strong call).
    """
    contradictions: list[dict] = []

    # 1. Pairwise topic stance opposition.
    for topic, row in disagreement_matrix.items():
        if topic.startswith("_") or row.get("_alignment") != "oppose":
            continue
        directional_models = [
            (m, s)
            for m, s in row.items()
            if not m.startswith("_") and s in ("bullish", "bearish")
        ]
        for i in range(len(directional_models)):
            for j in range(i + 1, len(directional_models)):
                a_model, a_stance = directional_models[i]
                b_model, b_stance = directional_models[j]
                if a_stance != b_stance:
                    contradictions.append(
                        {
                            "type": "pair_topic",
                            "topic": topic,
                            "model_a": a_model,
                            "model_b": b_model,
                            "stance_a": a_stance,
                            "stance_b": b_stance,
                            "severity": "high" if {a_stance, b_stance} == {"bullish", "bearish"} else "medium",
                        }
                    )

    # 2. Stance-vs-evidence mismatch — model's headline stance vs the
    #    dominant tilt of the risks they surfaced.
    bearish_topics = {"regulation", "advertising"}  # historically negative
    for model, op in round1.items():
        if op.error:
            continue
        model_risk_topics: list[str] = []
        for c in clusters:
            if model in c.support_models:
                model_risk_topics.append(c.topic)
        bearish_share = (
            sum(1 for t in model_risk_topics if t in bearish_topics)
            / max(len(model_risk_topics), 1)
        )
        if op.stance == "bullish" and bearish_share >= 0.5 and len(model_risk_topics) >= 2:
            contradictions.append(
                {
                    "type": "stance_vs_evidence",
                    "model_a": model,
                    "stance_a": op.stance,
                    "topic": "advertising/regulation",
                    "evidence_refs": sorted(set(model_risk_topics)),
                    "severity": "medium",
                    "note": (
                        "Headline stance is bullish but the model's own clustered risks "
                        "are dominated by bearish topics (ads / regulation)."
                    ),
                }
            )
        if op.stance == "bearish" and bearish_share <= 0.2 and len(model_risk_topics) >= 2:
            contradictions.append(
                {
                    "type": "stance_vs_evidence",
                    "model_a": model,
                    "stance_a": op.stance,
                    "topic": "macro/ai",
                    "evidence_refs": sorted(set(model_risk_topics)),
                    "severity": "low",
                    "note": (
                        "Headline stance is bearish but the model's clustered risks "
                        "are dominated by macro / AI topics — directional signal weak."
                    ),
                }
            )

    # 3. High confidence on top of low panel-wide reasoning overlap.
    if reasoning_overlap < 0.15:
        for model, op in round1.items():
            if op.error:
                continue
            if op.confidence >= 0.7:
                contradictions.append(
                    {
                        "type": "confidence_vs_reasoning",
                        "model_a": model,
                        "stance_a": op.stance,
                        "severity": "medium",
                        "note": (
                            f"{model} reports {op.confidence:.0%} confidence while panel "
                            f"reasoning overlap is only {reasoning_overlap:.0%} — the "
                            f"high confidence is not supported by shared evidence."
                        ),
                    }
                )

    severity_order = {"high": 0, "medium": 1, "low": 2}
    contradictions.sort(key=lambda c: severity_order.get(c.get("severity", "low"), 99))
    return contradictions


def build_conviction_heatmap(
    round1: dict[str, IndependentOpinion],
    disagreement_matrix: dict[str, dict[str, str]],
    clusters: list[RiskCluster],
) -> dict:
    """Per topic × model matrix of stance / confidence / risk_score.

    Topics come from the existing disagreement matrix (so we stay aligned
    with the legacy panel). ``risk_score`` is the number of clusters that
    a given model contributed to whose ``topic`` matches the row topic,
    normalized by max risks-per-model in that topic.
    """
    valid_models = [m for m, op in round1.items() if not op.error]
    topics = [t for t in disagreement_matrix if not t.startswith("_")]
    if not topics or not valid_models:
        return {"topics": [], "models": [], "cells": {}}

    risk_per_topic_model: dict[str, dict[str, int]] = {t: {m: 0 for m in valid_models} for t in topics}
    for cluster in clusters:
        if cluster.topic in risk_per_topic_model:
            for m in cluster.support_models:
                if m in risk_per_topic_model[cluster.topic]:
                    risk_per_topic_model[cluster.topic][m] += 1

    cells: dict[str, dict[str, dict]] = {}
    for topic in topics:
        row = disagreement_matrix.get(topic, {})
        max_risk_in_topic = max([1, *risk_per_topic_model[topic].values()])
        topic_cells: dict[str, dict] = {}
        for model in valid_models:
            op = round1[model]
            stance = row.get(model, op.stance)
            risk_count = risk_per_topic_model[topic][model]
            topic_cells[model] = {
                "stance": stance,
                "confidence": round(op.confidence, 3),
                "risk_score": round(risk_count / max_risk_in_topic, 3) if max_risk_in_topic else 0.0,
            }
        cells[topic] = topic_cells

    return {"topics": topics, "models": valid_models, "cells": cells}
