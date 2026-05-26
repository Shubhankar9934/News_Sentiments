"""Per-article ticker-relevance classifier.

Deterministic rules, no LLM calls. Returns one of four tiers with a score
and human-readable reasons so the UI can render badges.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

from app.services.relevance.sector_map import (
    MACRO_KEYWORDS,
    aliases_for,
    peers_for,
)

RelevanceTier = Literal["direct", "related_sector", "macro", "unrelated"]


@dataclass
class RelevanceResult:
    tier: RelevanceTier
    score: float
    reasons: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {"tier": self.tier, "score": round(self.score, 3), "reasons": self.reasons[:3]}


def _normalize(text: str | None) -> str:
    return (text or "").lower()


def _contains_alias(text: str, aliases: Iterable[str]) -> str | None:
    for alias in aliases:
        if not alias:
            continue
        if alias in text:
            return alias
    return None


def _peer_hit(text: str, peers: Iterable[str]) -> str | None:
    for peer in peers:
        # peers come from SECTOR_PEERS as uppercase tickers; match lowercase + uppercase
        # plus the alias list of each peer where it exists.
        plower = peer.lower()
        if plower in text:
            return peer
        for alias in aliases_for(peer):
            if alias in text and alias != plower:
                return peer
    return None


def _macro_hit(text: str) -> str | None:
    for kw in MACRO_KEYWORDS:
        if kw in text:
            return kw
    return None


def classify_article(
    headline: str | None,
    content: str | None,
    ticker: str,
) -> RelevanceResult:
    """Classify a single article. ``content`` may be empty — we lean on headline."""
    aliases = aliases_for(ticker)
    peers = peers_for(ticker)
    # Look at headline first, then content (limited to first ~600 chars to bound work).
    head_text = _normalize(headline)
    body_text = _normalize(content)[:600]

    reasons: list[str] = []

    direct_hit = _contains_alias(head_text, aliases) or _contains_alias(body_text, aliases)
    if direct_hit:
        reasons.append(f"mentions '{direct_hit}'")
        return RelevanceResult(tier="direct", score=1.0, reasons=reasons)

    peer_hit = _peer_hit(head_text, peers) or _peer_hit(body_text, peers)
    if peer_hit:
        reasons.append(f"sector peer {peer_hit}")
        return RelevanceResult(tier="related_sector", score=0.7, reasons=reasons)

    macro_hit = _macro_hit(head_text) or _macro_hit(body_text)
    if macro_hit:
        reasons.append(f"macro keyword '{macro_hit}'")
        return RelevanceResult(tier="macro", score=0.4, reasons=reasons)

    return RelevanceResult(tier="unrelated", score=0.0, reasons=["no ticker / peer / macro match"])


def classify_many(
    articles: Iterable[tuple[str | None, str | None]],
    ticker: str,
) -> list[RelevanceResult]:
    """Classify many ``(headline, content)`` tuples for ``ticker``."""
    return [classify_article(h, c, ticker) for h, c in articles]
