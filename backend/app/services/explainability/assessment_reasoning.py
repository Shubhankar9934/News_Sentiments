"""Assessment-team reasoning explainability block.

Stitches the per-member ``risk_lenses`` returned by the Assessment Team
into a 5-lens consensus view that the report panel renders.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.services.dashboard.schemas import (
    AssessmentReasoningExplain,
    AssessmentReasoningLens,
)

_LENS_KEYS = (
    "ticker_risk",
    "structure_risk",
    "position_risk",
    "historical_analogs",
    "macro_transmission",
)


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _collect_lenses(round1: dict[str, Any]) -> dict[str, list[tuple[str, str]]]:
    """Collect per-lens snippets keyed by member label."""

    buckets: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for role_key, member in (round1 or {}).items():
        member_d = _safe_dict(member)
        label = member_d.get("assessment_label") or role_key
        lenses = _safe_dict(member_d.get("risk_lenses"))
        for key in _LENS_KEYS:
            text = lenses.get(key)
            if isinstance(text, str) and text.strip():
                buckets[key].append((label, text.strip()[:600]))
    return buckets


def _consensus_summary(snippets: list[tuple[str, str]]) -> str:
    if not snippets:
        return ""
    # Naive consensus: first 1–2 distinct sentences joined.
    seen: set[str] = set()
    out: list[str] = []
    for _, text in snippets:
        head = text.split(". ")[0].strip()
        if head and head not in seen:
            seen.add(head)
            out.append(head)
        if len(out) >= 2:
            break
    summary = ". ".join(out)
    if summary and not summary.endswith("."):
        summary += "."
    return summary[:500]


def build_assessment_reasoning(
    *,
    ticker: str,  # noqa: ARG001
    deliberation_layer: dict[str, Any] | None,
) -> AssessmentReasoningExplain | None:
    if not deliberation_layer:
        return None
    assessment_layer = _safe_dict(deliberation_layer.get("assessment_layer"))
    if not assessment_layer:
        return None

    # Prefer the revised opinions from round 3 (post-critique) when available.
    round1 = _safe_dict(assessment_layer.get("round1"))
    round3 = _safe_dict(assessment_layer.get("round3"))
    used_round = round1
    if round3:
        revised: dict[str, Any] = {}
        for role, payload in round3.items():
            rev_opinion = _safe_dict(payload).get("revised_opinion")
            if rev_opinion:
                revised[role] = rev_opinion
            else:
                revised[role] = round1.get(role) or {}
        if revised:
            used_round = revised

    buckets = _collect_lenses(used_round)

    lenses: list[AssessmentReasoningLens] = []
    members_used: set[str] = set()
    for key in _LENS_KEYS:
        snippets = buckets.get(key, [])
        if not snippets:
            continue
        summary = _consensus_summary(snippets)
        member_views = [f"{label}: {text}" for label, text in snippets[:3]]
        members_used.update(label for label, _ in snippets)
        lenses.append(
            AssessmentReasoningLens(
                lens=key,  # type: ignore[arg-type]
                summary=summary or "No consensus reasoning available.",
                member_views=member_views,
            )
        )

    if not lenses:
        return None

    return AssessmentReasoningExplain(
        lenses=lenses,
        members_used=sorted(members_used),
    )
