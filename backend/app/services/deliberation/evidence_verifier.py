"""Evidence verification stub.

Reserves the integration point for a future evidence-verification layer
without changing the orchestrator's external contract today. When the flag
``DIL_USE_EVIDENCE_VERIFICATION`` is on, the stub extracts the numeric and
named-source claims from each model's reasoning steps and key risks, then
emits an ``evidence_verification`` list where every claim is marked as
``unverified``. A future implementation will cross-check each claim against
the ``article_evidence`` payload (already in the deliberation context) and
flip the status to ``verified`` / ``partial`` accordingly.

Schema (kept stable from the start so future fills are non-breaking):

    {
        "id": "evi-001",
        "claim": "Alphabet relies on ad revenue for ~75% of top line",
        "source_title": null,
        "source_url": null,
        "status": "unverified",
        "supporting_models": ["claude", "deepseek"],
        "contradicting_models": []
    }
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from app.services.deliberation.schemas import IndependentOpinion

# Heuristic claim markers — numbers, percents, "Trade Desk says", named sources.
_NUMERIC_RE = re.compile(r"(\d+(?:\.\d+)?\s*%)|(\$\d[\d,]*(?:\.\d+)?\b)|(\d[\d,]*\s*(?:bps|basis points|million|billion|trillion))")
_SAID_RE = re.compile(r"\b([A-Z][a-zA-Z\.&'\- ]{2,40})\s+(said|stated|reported|warned|guided|noted|flagged)", re.I)

_MAX_CLAIMS = 25


@dataclass
class EvidenceClaim:
    id: str
    claim: str
    source_title: str | None
    source_url: str | None
    status: str
    supporting_models: list[str]
    contradicting_models: list[str]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "claim": self.claim,
            "source_title": self.source_title,
            "source_url": self.source_url,
            "status": self.status,
            "supporting_models": list(self.supporting_models),
            "contradicting_models": list(self.contradicting_models),
        }


def _extract_claims(text: str) -> list[str]:
    if not text:
        return []
    claims: list[str] = []
    # Number-bearing sentences
    for sentence in re.split(r"(?<=[\.!?])\s+", text):
        if _NUMERIC_RE.search(sentence) or _SAID_RE.search(sentence):
            cleaned = sentence.strip().rstrip(".")
            if cleaned and len(cleaned) > 10:
                claims.append(cleaned)
    return claims


def extract_evidence_claims(
    round1: dict[str, IndependentOpinion],
) -> list[EvidenceClaim]:
    """Aggregate every numeric / source-bearing claim across models.

    Claims are deduplicated by canonical form (lowercased, whitespace
    collapsed) and tagged with which models surfaced them.
    """
    canonical_to_claim: dict[str, EvidenceClaim] = {}
    counter = 0
    supporting: defaultdict[str, set[str]] = defaultdict(set)
    for model, op in round1.items():
        if op.error:
            continue
        for step in op.reasoning_steps:
            for c in _extract_claims(step.analysis):
                key = re.sub(r"\s+", " ", c.lower())
                if key not in canonical_to_claim:
                    counter += 1
                    canonical_to_claim[key] = EvidenceClaim(
                        id=f"evi-{counter:03d}",
                        claim=c,
                        source_title=None,
                        source_url=None,
                        status="unverified",
                        supporting_models=[],
                        contradicting_models=[],
                    )
                supporting[key].add(model)
        for risk in op.key_risks:
            for c in _extract_claims(risk):
                key = re.sub(r"\s+", " ", c.lower())
                if key not in canonical_to_claim:
                    counter += 1
                    canonical_to_claim[key] = EvidenceClaim(
                        id=f"evi-{counter:03d}",
                        claim=c,
                        source_title=None,
                        source_url=None,
                        status="unverified",
                        supporting_models=[],
                        contradicting_models=[],
                    )
                supporting[key].add(model)
    for key, models in supporting.items():
        canonical_to_claim[key].supporting_models = sorted(models)
    out = list(canonical_to_claim.values())
    out.sort(key=lambda c: (-len(c.supporting_models), c.id))
    return out[:_MAX_CLAIMS]


class EvidenceVerifier:
    """Stub verifier — every claim returns ``unverified``.

    The orchestrator calls ``verify(round1)`` only when the
    ``DIL_USE_EVIDENCE_VERIFICATION`` flag is enabled. A future
    implementation will swap in a real claim-vs-article cross-checker.
    """

    def verify(self, round1: dict[str, IndependentOpinion]) -> list[dict]:
        claims = extract_evidence_claims(round1)
        return [c.to_dict() for c in claims]
