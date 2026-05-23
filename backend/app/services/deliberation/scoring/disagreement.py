"""Disagreement matrix and topology metrics."""

from __future__ import annotations

import re
from typing import Any

from app.services.deliberation.schemas import DebateCritique, DeliberationMetrics, IndependentOpinion, ModelKey

TOPICS = ("macro", "earnings", "volatility", "valuation", "liquidity")

TOPIC_KEYWORDS: dict[str, re.Pattern[str]] = {
    "macro": re.compile(r"macro|fed|rates|inflation|gdp|economy|geopolit", re.I),
    "earnings": re.compile(r"earn|eps|revenue|guidance|quarter|profit", re.I),
    "volatility": re.compile(r"volatil|vix|beta|swing|regime", re.I),
    "valuation": re.compile(r"valuat|multiple|pe\b|price.target|fair.value", re.I),
    "liquidity": re.compile(r"liquid|volume|flow|spread|bid", re.I),
}


def _topic_stance_from_text(text: str, default_stance: str) -> str:
    """Heuristic topic-level stance from a snippet of reasoning or risk text.

    Note: ``risk`` was previously a bearish marker, which forced every topic
    that quoted the word "risk" to flip to bearish even in clearly bullish
    contexts. PR5 removes that conflation — risks are now considered
    bidirectional and require an explicit directional marker. Both
    ``bullish/bearish`` markers are detected; if both appear, default stance
    wins (the snippet is genuinely mixed).
    """
    t = text.lower()
    bullish_markers = any(
        w in t for w in ("bullish", "positive", "upside", "buy ", "tailwind", "supportive")
    )
    bearish_markers = any(
        w in t for w in ("bearish", "negative", "downside", "sell ", "headwind", "weak ")
    )
    if bullish_markers and not bearish_markers:
        return "bullish"
    if bearish_markers and not bullish_markers:
        return "bearish"
    return default_stance


def _extract_topic_views(opinion: IndependentOpinion) -> dict[str, str]:
    default = opinion.stance
    views: dict[str, str] = {topic: default for topic in TOPICS}
    for step in opinion.reasoning_steps:
        blob = f"{step.title} {step.analysis}"
        for topic, pattern in TOPIC_KEYWORDS.items():
            if pattern.search(blob):
                views[topic] = _topic_stance_from_text(blob, default)
    for risk in opinion.key_risks:
        for topic, pattern in TOPIC_KEYWORDS.items():
            if pattern.search(risk):
                views[topic] = _topic_stance_from_text(risk, views[topic])
    return views


def _cell_alignment(values: list[str]) -> str:
    if len(values) < 2:
        return "agree"
    uniq = set(values)
    if len(uniq) == 1:
        return "agree"
    if len(uniq) == 2 and "neutral" in uniq:
        return "split"
    return "oppose"


def build_disagreement_matrix(
    round1: dict[str, IndependentOpinion],
) -> dict[str, dict[str, str]]:
    model_views: dict[str, dict[str, str]] = {}
    for model, opinion in round1.items():
        if opinion.error:
            continue
        model_views[model] = _extract_topic_views(opinion)

    matrix: dict[str, dict[str, str]] = {}
    for topic in TOPICS:
        row: dict[str, str] = {}
        stances = []
        for model, views in model_views.items():
            cell = views.get(topic, "neutral")
            row[model] = cell
            stances.append(cell)
        row["_alignment"] = _cell_alignment(stances)
        matrix[topic] = row
    return matrix


def _token_set(texts: list[str]) -> set[str]:
    tokens: set[str] = set()
    for t in texts:
        for w in re.findall(r"[a-z]{4,}", t.lower()):
            tokens.add(w)
    return tokens


def reasoning_overlap(round1: dict[str, IndependentOpinion]) -> float:
    sets = []
    for op in round1.values():
        if op.error:
            continue
        texts = [s.analysis for s in op.reasoning_steps] + op.key_risks
        sets.append(_token_set(texts))
    if len(sets) < 2:
        return 1.0
    overlaps = []
    keys = list(sets)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            if not a and not b:
                continue
            union = a | b
            overlaps.append(len(a & b) / len(union) if union else 0.0)
    return round(sum(overlaps) / len(overlaps), 3) if overlaps else 0.0


def model_divergence(round1: dict[str, IndependentOpinion]) -> float:
    from app.services.deliberation.scoring.weighting import stance_to_score

    scores = [stance_to_score(o.stance) for o in round1.values() if not o.error]
    if len(scores) < 2:
        return 0.0
    mean = sum(scores) / len(scores)
    return round((sum((s - mean) ** 2 for s in scores) / len(scores)) ** 0.5, 3)


def confidence_spread(round1: dict[str, IndependentOpinion]) -> float:
    confs = [o.confidence for o in round1.values() if not o.error]
    if len(confs) < 2:
        return 0.0
    return round(max(confs) - min(confs), 3)


def contradiction_density(
    round1: dict[str, IndependentOpinion],
    debate_rounds: list[dict[str, DebateCritique]],
) -> float:
    oppose_cells = 0
    total = 0
    matrix = build_disagreement_matrix(round1)
    for topic, row in matrix.items():
        if topic.startswith("_"):
            continue
        align = row.get("_alignment", "agree")
        total += 1
        if align == "oppose":
            oppose_cells += 1
    debate_disagrees = sum(
        len(c.disagrees_with)
        for rd in debate_rounds
        for c in rd.values()
        if not c.error
    )
    denom = max(total + len(debate_rounds), 1)
    return round((oppose_cells + debate_disagrees * 0.25) / denom, 3)


def main_conflicts(matrix: dict[str, dict[str, str]]) -> list[str]:
    conflicts: list[str] = []
    for topic, row in matrix.items():
        if row.get("_alignment") == "oppose":
            models = {k: v for k, v in row.items() if not k.startswith("_")}
            conflicts.append(f"{topic}: {models}")
    return conflicts


def build_metrics(
    round1: dict[str, IndependentOpinion],
    debate_rounds: list[dict[str, DebateCritique]],
) -> DeliberationMetrics:
    from app.services.deliberation.scoring.confidence_drift import compute_confidence_drift
    from app.services.deliberation.scoring.novelty import score_round_novelty
    from app.services.deliberation.scoring.risk_clustering import cluster_risks
    from app.services.deliberation.scoring.topology import (
        build_conviction_heatmap,
        build_disagreement_topology,
        detect_contradictions,
    )

    matrix = build_disagreement_matrix(round1)
    round_novelty: list[dict] = []
    if len(debate_rounds) >= 2:
        novelty_scores = score_round_novelty(debate_rounds[0], debate_rounds[1])
        round_novelty = [s.to_dict() for s in novelty_scores]
    clusters = cluster_risks(round1, debate_rounds)
    topology = build_disagreement_topology(round1, matrix, clusters)
    heatmap = build_conviction_heatmap(round1, matrix, clusters)
    overlap = reasoning_overlap(round1)
    contradictions = detect_contradictions(round1, matrix, clusters, overlap)
    return DeliberationMetrics(
        disagreement_matrix=matrix,
        confidence_drift=compute_confidence_drift(round1, debate_rounds),
        model_divergence=model_divergence(round1),
        confidence_spread=confidence_spread(round1),
        contradiction_density=contradiction_density(round1, debate_rounds),
        reasoning_overlap=overlap,
        round_novelty=round_novelty,
        disagreement_topology=topology,
        conviction_heatmap=heatmap,
        contradictions=contradictions,
    )
