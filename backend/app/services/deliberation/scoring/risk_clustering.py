"""Deterministic risk deduplication & clustering.

The default hidden-risks pipeline deduplicates only by exact lowercased
string match. In production, four models routinely produce ~5 paraphrases
each of the same underlying risk ("Trade Desk warning hurts ad revenue"
might appear as "Trade Desk's cautious outlook on the ad market", "Trade
Desk concerns broaden to sector ad re-rating", etc.). Users see ~20 bullets
that collapse to ~5 themes.

This module clusters those raw risk strings into:

- a canonical ``headline`` (the most descriptive representative)
- ``members`` — every raw phrasing that mapped to the cluster
- ``support_models`` — which models surfaced this cluster (drives severity)
- ``severity`` — derived from support count and ``invalidator`` membership
- ``topic`` — best-guess topic via the same regex registry used elsewhere

Clustering is greedy agglomerative on token-set Jaccard plus a shared
entity-bigram match (e.g. ``trade desk``, ``ad market``), with no LLM
calls. Determinism matters: the same input always produces the same
clusters so the consensus layer remains auditable.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from app.services.deliberation.schemas import DebateCritique, IndependentOpinion

# Words too generic to differentiate clusters.
_STOPWORDS: set[str] = {
    "with", "from", "that", "this", "have", "will", "could", "would", "should",
    "their", "there", "these", "those", "into", "onto", "than", "then", "very",
    "more", "less", "much", "some", "many", "much", "most", "least",
    "about", "such", "what", "when", "where", "which", "while", "still",
    "been", "being", "above", "below", "near", "also", "even", "just", "only",
    "risk", "risks", "concern", "concerns", "issue", "issues",
}

_WORD_RE = re.compile(r"[a-z][a-z\-']{2,}")

# Domain entities that, when present in both candidates, force a cluster
# merge regardless of overall Jaccard score. Order-sensitive to allow
# multi-word entities to be detected before single-word fragments.
_DOMAIN_ENTITIES: tuple[str, ...] = (
    "trade desk",
    "ad market",
    "ad revenue",
    "digital advertising",
    "magnificent seven",
    "borrowing costs",
    "google cloud",
    "rate cut",
    "rate hike",
    "regulatory",
    "antitrust",
    "earnings miss",
    "earnings beat",
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
    "guidance",
)

# Topic keywords (kept aligned with scoring.disagreement.TOPIC_KEYWORDS).
_TOPIC_KEYWORDS: dict[str, re.Pattern[str]] = {
    "macro": re.compile(r"macro|fed|rates|inflation|gdp|economy|geopolit|borrow", re.I),
    "earnings": re.compile(r"earn|eps|revenue|guidance|quarter|profit", re.I),
    "volatility": re.compile(r"volatil|vix|beta|swing|regime", re.I),
    "valuation": re.compile(r"valuat|multiple|price.target|fair.value|expensive|cheap", re.I),
    "liquidity": re.compile(r"liquid|volume|flow|spread|bid|ask", re.I),
    "regulation": re.compile(r"regulator|antitrust|lawsuit|doj|sec\b|ftc", re.I),
    "advertising": re.compile(r"\b(ad|ads|advertis|ad market)\b", re.I),
    "ai": re.compile(r"\bai\b|llm|gpu|nvidia|infrastructure|capex", re.I),
}


@dataclass
class _Candidate:
    text: str
    tokens: set[str]
    entities: set[str]
    source_model: str
    source_kind: str  # "key_risk" | "hidden_assumption" | "new_risk" | "invalidator"


@dataclass
class RiskCluster:
    cluster_id: str
    headline: str
    members: list[str] = field(default_factory=list)
    support_models: list[str] = field(default_factory=list)
    support_count: int = 0
    severity: str = "low"
    topic: str = "other"

    def to_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "headline": self.headline,
            "members": list(self.members),
            "support_models": list(self.support_models),
            "support_count": self.support_count,
            "severity": self.severity,
            "topic": self.topic,
        }


def _tokenize(text: str) -> set[str]:
    if not text:
        return set()
    return {
        w
        for w in _WORD_RE.findall(text.lower())
        if w not in _STOPWORDS
    }


def _entities(text: str) -> set[str]:
    t = text.lower()
    return {ent for ent in _DOMAIN_ENTITIES if ent in t}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _topic_of(text: str) -> str:
    for topic, pat in _TOPIC_KEYWORDS.items():
        if pat.search(text):
            return topic
    return "other"


def _should_merge(a: _Candidate, b: _Candidate, *, jaccard_threshold: float) -> bool:
    if a.entities and b.entities and (a.entities & b.entities):
        # Sharing a domain entity is a strong cluster signal even if other
        # words diverge (e.g. "Trade Desk warning" vs "Trade Desk's outlook").
        return True
    return _jaccard(a.tokens, b.tokens) >= jaccard_threshold


def _collect_candidates(
    round1: dict[str, IndependentOpinion],
    debate_rounds: list[dict[str, DebateCritique]],
) -> list[_Candidate]:
    out: list[_Candidate] = []
    for model, op in round1.items():
        if op.error:
            continue
        for r in op.key_risks:
            if r and r.strip():
                out.append(
                    _Candidate(
                        text=r.strip(),
                        tokens=_tokenize(r),
                        entities=_entities(r),
                        source_model=model,
                        source_kind="key_risk",
                    )
                )
        for r in op.hidden_assumptions:
            if r and r.strip():
                out.append(
                    _Candidate(
                        text=r.strip(),
                        tokens=_tokenize(r),
                        entities=_entities(r),
                        source_model=model,
                        source_kind="hidden_assumption",
                    )
                )
        for r in op.invalidators:
            if r and r.strip():
                out.append(
                    _Candidate(
                        text=r.strip(),
                        tokens=_tokenize(r),
                        entities=_entities(r),
                        source_model=model,
                        source_kind="invalidator",
                    )
                )
    for rd in debate_rounds:
        for model, c in rd.items():
            if c.error:
                continue
            for r in c.new_risks_identified:
                if r and r.strip():
                    out.append(
                        _Candidate(
                            text=r.strip(),
                            tokens=_tokenize(r),
                            entities=_entities(r),
                            source_model=model,
                            source_kind="new_risk",
                        )
                    )
    return out


def _pick_headline(members: list[_Candidate]) -> str:
    """Choose the most informative representative for the cluster.

    Prefer the longest member that contains at least one domain entity; fall
    back to the longest member overall. Deterministic on ties via the model
    id alphabetical order.
    """
    def sort_key(c: _Candidate) -> tuple:
        return (
            -len(c.entities),  # most entities first
            -len(c.text),      # then longest text
            c.source_model,    # then alphabetical model id for stability
        )

    ordered = sorted(members, key=sort_key)
    return ordered[0].text if ordered else ""


def _severity(cluster: list[_Candidate], support_models: list[str]) -> str:
    has_invalidator = any(c.source_kind == "invalidator" for c in cluster)
    if has_invalidator or len(support_models) >= 3:
        return "high"
    if len(support_models) == 2:
        return "medium"
    return "low"


def cluster_risks(
    round1: dict[str, IndependentOpinion],
    debate_rounds: list[dict[str, DebateCritique]],
    *,
    jaccard_threshold: float = 0.4,
    max_clusters: int = 12,
) -> list[RiskCluster]:
    """Greedy agglomerative clustering of risks across models and rounds.

    Returns clusters sorted by (support_count desc, severity desc, headline).
    """
    candidates = _collect_candidates(round1, debate_rounds)
    if not candidates:
        return []

    clusters: list[list[_Candidate]] = []
    for cand in candidates:
        placed = False
        for cluster in clusters:
            # Compare against the cluster representative (first member) to
            # keep clustering O(n * k); k is small in practice.
            rep = cluster[0]
            if _should_merge(rep, cand, jaccard_threshold=jaccard_threshold):
                cluster.append(cand)
                placed = True
                break
        if not placed:
            clusters.append([cand])

    out: list[RiskCluster] = []
    for idx, group in enumerate(clusters):
        models_in_cluster = sorted({c.source_model for c in group})
        headline = _pick_headline(group)
        members = []
        seen: set[str] = set()
        for c in group:
            key = c.text.strip().lower()
            if key not in seen:
                seen.add(key)
                members.append(c.text)
        out.append(
            RiskCluster(
                cluster_id=f"risk-{idx + 1:02d}",
                headline=headline,
                members=members,
                support_models=models_in_cluster,
                support_count=len(models_in_cluster),
                severity=_severity(group, models_in_cluster),
                topic=_topic_of(headline),
            )
        )

    severity_order = {"high": 0, "medium": 1, "low": 2}
    out.sort(
        key=lambda c: (
            -c.support_count,
            severity_order.get(c.severity, 99),
            c.headline.lower(),
        )
    )
    return out[:max_clusters]


def cluster_headlines(clusters: list[RiskCluster]) -> list[str]:
    """Legacy back-compat: derive the flat ``hidden_risks: list[str]`` from
    clusters so existing UI keeps rendering when the backend opts into
    clustering."""
    return [c.headline for c in clusters if c.headline]


def cluster_summary(clusters: list[RiskCluster]) -> dict[str, int]:
    """Aggregate counts by severity for telemetry / UI badges."""
    counts: Counter[str] = Counter(c.severity for c in clusters)
    return {
        "high": counts.get("high", 0),
        "medium": counts.get("medium", 0),
        "low": counts.get("low", 0),
        "total": len(clusters),
    }
