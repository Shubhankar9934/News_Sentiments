"""Thesis clustering — collapse per-model opinions into bull/bear/neutral
narrative groups.

The default UI shows four parallel opinion cards; humans then have to
mentally cluster them by direction. This module does the clustering
deterministically and exposes:

- ``stance`` — bullish / bearish / neutral / mixed
- ``models`` — which model ids hold this thesis
- ``bullets`` — the most informative reasoning headlines from those models
- ``summary`` — rule-based: the most-cited domain entities joined into a
  one-line headline (no LLM call)
- ``support_count`` — len(models)

Clusters are sorted by support_count desc so the dominant thesis renders
first. ``mixed`` and ``neutral`` are kept distinct (mirroring the rest of
the scoring stack).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from app.services.deliberation.schemas import IndependentOpinion

# Same domain-entity list used in risk clustering — keeps thesis summaries
# semantically aligned with the risk panel.
_DOMAIN_ENTITIES: tuple[str, ...] = (
    "trade desk",
    "ad market",
    "ad revenue",
    "digital advertising",
    "magnificent seven",
    "borrowing costs",
    "google cloud",
    "nvidia",
    "rate cut",
    "rate hike",
    "regulatory",
    "antitrust",
    "earnings",
    "guidance",
    "waymo",
    "robotaxi",
    "moonshot",
    "rotation",
    "volatility",
    "valuation",
    "ai capex",
    "ai infrastructure",
    "ai demand",
    "supply chain",
    "macro",
    "dow",
    "risk-on",
    "risk-off",
)

_HEADLINE_LIMIT = 6


@dataclass
class ThesisCluster:
    stance: str
    models: list[str] = field(default_factory=list)
    bullets: list[str] = field(default_factory=list)
    summary: str = ""
    support_count: int = 0

    def to_dict(self) -> dict:
        return {
            "stance": self.stance,
            "models": list(self.models),
            "bullets": list(self.bullets),
            "summary": self.summary,
            "support_count": self.support_count,
        }


def _extract_entities(text: str) -> list[str]:
    t = text.lower()
    return [e for e in _DOMAIN_ENTITIES if e in t]


def _entity_summary(opinions: list[IndependentOpinion]) -> str:
    counts: Counter[str] = Counter()
    for op in opinions:
        for step in op.reasoning_steps:
            for ent in _extract_entities(f"{step.title} {step.analysis}"):
                counts[ent] += 1
        for risk in op.key_risks:
            for ent in _extract_entities(risk):
                counts[ent] += 1
    top = [ent for ent, _ in counts.most_common(3)]
    if not top:
        return ""
    return " · ".join(t.title() for t in top)


def _select_bullets(opinions: list[IndependentOpinion]) -> list[str]:
    """Pick up to N reasoning headlines, preferring those that mention a
    domain entity. Falls back to first available titles."""
    scored: list[tuple[int, str, str]] = []
    for op in opinions:
        for step in op.reasoning_steps:
            entity_count = len(_extract_entities(f"{step.title} {step.analysis}"))
            scored.append((entity_count, op.model, step.title.strip()))
    # Sort by entity richness desc, then model alphabetical for stability.
    scored.sort(key=lambda x: (-x[0], x[1]))
    seen: set[str] = set()
    out: list[str] = []
    for _, model, title in scored:
        if not title:
            continue
        key = re.sub(r"\W+", "", title.lower())[:48]
        if key in seen:
            continue
        seen.add(key)
        out.append(title)
        if len(out) >= _HEADLINE_LIMIT:
            break
    return out


def build_thesis_clusters(
    round1: dict[str, IndependentOpinion],
) -> list[ThesisCluster]:
    by_stance: dict[str, list[IndependentOpinion]] = {}
    for model, op in round1.items():
        if op.error:
            continue
        by_stance.setdefault(op.stance, []).append(op)

    clusters: list[ThesisCluster] = []
    for stance, ops in by_stance.items():
        clusters.append(
            ThesisCluster(
                stance=stance,
                models=sorted(o.model for o in ops),
                bullets=_select_bullets(ops),
                summary=_entity_summary(ops),
                support_count=len(ops),
            )
        )

    # Order: dominant thesis first (most supporters), then by stance preference
    # so directional clusters appear before mixed/neutral when tied.
    stance_order = {"bullish": 0, "bearish": 1, "mixed": 2, "neutral": 3}
    clusters.sort(
        key=lambda c: (
            -c.support_count,
            stance_order.get(c.stance, 99),
        )
    )
    return clusters
