"""Decision Justification post-processor (Phase 9).

Pure read-side helper. Given a populated ``council_layer`` it composes
the report panel payload — vote table, primary reasons, dissent and
main conflict — without calling any LLM.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from app.services.dashboard.schemas import (
    CouncilVoteRow,
    DecisionJustificationExplain,
    ReverseBwbSummary,
)


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


_THEME_PATTERNS: list[tuple[str, str]] = [
    ("pin risk", r"pin\s*[-_ ]?risk|gamma pin|round[- ]number pin"),
    ("body placement", r"body\s+placement|short\s+body|body\s+strike|body\s+exposure"),
    ("credit efficiency", r"credit\s+(efficiency|too\s+small|insufficient)"),
    ("event uncertainty", r"event\s+(risk|uncertainty)|catalyst|fomc|cpi|earnings"),
    ("liquidity drag", r"liquid|spread|execution"),
    ("structural geometry", r"wing\s+width|wing\s+protection|risk[- ]reward"),
    ("vol regime", r"volatil|sigma|regime"),
    ("macro risk", r"macro|rates|inflation|fed|yield"),
    ("tail risk", r"tail|left[- ]tail|max[- ]?loss"),
    ("probability of touch", r"probability\s+of\s+touch|p[- ]?o[- ]?t|touch\s+the\s+body"),
]


def _extract_themes(snippets: list[str], top_k: int = 4) -> list[str]:
    counter: Counter[str] = Counter()
    for snippet in snippets:
        text = (snippet or "").lower()
        for theme, pattern in _THEME_PATTERNS:
            if re.search(pattern, text):
                counter[theme] += 1
    return [theme for theme, _ in counter.most_common(top_k)]


def build_decision_justification(
    *,
    ticker: str,  # noqa: ARG001
    deliberation_layer: dict[str, Any] | None,
    summary: ReverseBwbSummary | None,
) -> DecisionJustificationExplain | None:
    if not deliberation_layer:
        return None
    council_layer = _safe_dict(deliberation_layer.get("council_layer"))
    if not council_layer:
        return None

    round1 = _safe_dict(council_layer.get("round1"))
    round3 = _safe_dict(council_layer.get("round3"))
    consensus = _safe_dict(council_layer.get("consensus"))

    if not round1 and not consensus:
        return None

    votes: list[CouncilVoteRow] = []
    risk_snippets: list[str] = []
    rationale_snippets: list[str] = []
    finals: dict[str, str] = {}

    for role_key, raw in round1.items():
        member = _safe_dict(raw)
        label = member.get("council_label") or role_key
        decision = str(member.get("decision") or "WAIT").upper()
        confidence = member.get("confidence")
        # Revised decision wins if present and not errored.
        revision = _safe_dict(round3.get(role_key))
        if revision and not revision.get("error"):
            revised_decision = revision.get("revised_decision")
            if revised_decision:
                decision = str(revised_decision).upper()
            revised_conf = revision.get("revised_confidence")
            if isinstance(revised_conf, (int, float)):
                confidence = float(revised_conf)
            rationale_snippets.append(str(revision.get("revision_rationale") or ""))

        finals[role_key] = decision
        for risk in member.get("key_risks") or []:
            if isinstance(risk, str) and risk.strip():
                risk_snippets.append(risk)

        # top_reason = first reasoning step title or analysis snippet
        top_reason = None
        for step in member.get("reasoning_steps") or []:
            if isinstance(step, dict):
                title = step.get("title") or ""
                analysis = step.get("analysis") or ""
                top_reason = (title or analysis)[:180]
                if top_reason:
                    break

        votes.append(
            CouncilVoteRow(
                member=str(member.get("model") or role_key),
                label=str(label),
                decision=decision,
                confidence=(
                    float(confidence)
                    if isinstance(confidence, (int, float))
                    else None
                ),
                top_reason=top_reason,
            )
        )

    consensus_decision = str(
        consensus.get("decision") or deliberation_layer.get("mapped_decision") or "WAIT"
    ).upper()
    if summary is not None:
        consensus_decision = summary.decision.upper()

    support = consensus.get("support")
    if not isinstance(support, dict):
        support = dict(Counter(finals.values()))

    primary_reasons = _extract_themes(risk_snippets + rationale_snippets, top_k=4)

    # Dissent: members whose final vote differed from consensus.
    dissent: list[str] = []
    for role_key, vote in finals.items():
        if vote != consensus_decision:
            member = _safe_dict(round1.get(role_key))
            label = member.get("council_label") or role_key
            dissent.append(f"{label} → {vote}")

    return DecisionJustificationExplain(
        council_votes=votes,
        consensus_decision=consensus_decision,
        support_counts={k: int(v) for k, v in (support or {}).items()},
        consensus_confidence=(
            float(consensus["confidence"])
            if isinstance(consensus.get("confidence"), (int, float))
            else None
        ),
        primary_reasons=primary_reasons,
        dissent=dissent,
        main_conflict=consensus.get("main_conflict"),
    )
