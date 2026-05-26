"""Macro transmission chain (Phase 6).

Deterministic builder that produces a causal chain like:

    Iran Peace Deal → Oil Down → Inflation Down → Yield Pressure Lower → Supportive For SPY

The chain skeleton is derived from a small topology table that maps
common macro shocks to their first-order asset reactions and the
ticker-level impact. The macro_desk LLM later reads this skeleton from
its context and produces a narrative; the final explainability block
combines both.

This module is pure read-side; no LLM calls. It is consumed by:

* :mod:`app.services.deliberation.desk_config` — feeding macro_desk via
  ``role_focus.macro_transmission``.
* :mod:`app.services.explainability.macro_transmission_explain` — which
  composes the report panel payload using the chain + macro_desk
  narrative.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class TransmissionNode:
    node: str
    label: str
    direction: str | None  # "up" | "down" | "flat" | "mixed" | None
    evidence: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# Topology table: keywords → first-order chain steps. Each entry maps a
# detected shock to a list of (node_id, default_label, default_direction)
# tuples. The ticker impact is appended last by the resolver.
_TRANSMISSION_TOPOLOGY: dict[str, list[tuple[str, str, str]]] = {
    # Geopolitical / energy
    "iran_conflict": [
        ("oil", "Oil Up", "up"),
        ("inflation", "Inflation Shock", "up"),
        ("yields", "Rates Higher", "up"),
    ],
    "iran_peace": [
        ("oil", "Oil Down", "down"),
        ("inflation", "Inflation Down", "down"),
        ("yields", "Yield Pressure Lower", "down"),
    ],
    "opec_cut": [
        ("oil", "Oil Up", "up"),
        ("inflation", "Inflation Up", "up"),
        ("yields", "Rates Higher", "up"),
    ],
    "oil_supply_glut": [
        ("oil", "Oil Down", "down"),
        ("inflation", "Inflation Eases", "down"),
        ("yields", "Yields Drift Lower", "down"),
    ],
    # Rates / Fed
    "fed_hawkish": [
        ("yields", "Rates Higher", "up"),
        ("dollar", "Dollar Stronger", "up"),
        ("liquidity", "Liquidity Tightens", "down"),
    ],
    "fed_dovish": [
        ("yields", "Rates Lower", "down"),
        ("dollar", "Dollar Weaker", "down"),
        ("liquidity", "Liquidity Eases", "up"),
    ],
    "inflation_print_hot": [
        ("yields", "Rates Higher", "up"),
        ("rate_cuts", "Cuts Repriced Out", "down"),
    ],
    "inflation_print_cool": [
        ("yields", "Rates Lower", "down"),
        ("rate_cuts", "Cuts Repriced In", "up"),
    ],
    # Risk-on / risk-off shocks
    "banking_stress": [
        ("credit_spreads", "Credit Spreads Wider", "up"),
        ("liquidity", "Liquidity Concerns", "down"),
    ],
    "tariff_shock": [
        ("trade", "Trade Frictions", "up"),
        ("inflation", "Imported Inflation", "up"),
        ("growth", "Growth Risk", "down"),
    ],
}


# Asset → ticker-class impact lookup.
_TICKER_IMPACT: dict[tuple[str, str], str] = {
    ("yields_up", "broad_equity"): "bearish",
    ("yields_down", "broad_equity"): "supportive",
    ("liquidity_up", "broad_equity"): "supportive",
    ("liquidity_down", "broad_equity"): "bearish",
    ("oil_up", "broad_equity"): "bearish",
    ("oil_down", "broad_equity"): "supportive",
    ("dollar_up", "broad_equity"): "bearish",
}


def _detect_shock(text: str) -> str | None:
    t = text.lower()
    if "iran" in t and any(w in t for w in ("peace", "deal", "ceasefire", "talks")):
        return "iran_peace"
    if "iran" in t and any(w in t for w in ("conflict", "strike", "war", "tension", "attack")):
        return "iran_conflict"
    if "opec" in t and any(w in t for w in ("cut", "reduce", "curtail")):
        return "opec_cut"
    if any(w in t for w in ("oil supply", "supply glut", "oil glut")):
        return "oil_supply_glut"
    has_fed_context = any(
        w in t for w in ("fomc", "fed", "powell", "rates", "rate path", "yield")
    )
    if has_fed_context:
        if any(w in t for w in ("hawkish", "hike", "tighten", "higher for longer")):
            return "fed_hawkish"
        if any(w in t for w in ("dovish", "rate cut", "pause", "ease")):
            return "fed_dovish"
    if "cpi" in t or "inflation" in t:
        if any(w in t for w in ("hot", "hotter", "above", "beat")):
            return "inflation_print_hot"
        if any(w in t for w in ("cool", "cooler", "below", "miss")):
            return "inflation_print_cool"
    if any(w in t for w in ("bank stress", "banking crisis", "regional bank")):
        return "banking_stress"
    if "tariff" in t:
        return "tariff_shock"
    return None


def _classify_ticker(ticker: str) -> str:
    """Map a ticker to a broad impact class.

    SPY/QQQ/IWM/DIA all map to ``broad_equity`` — the topology covers
    broad-market transmission today. Single-name tickers fall through
    to ``broad_equity`` as a safe default; the LLM narrative will refine.
    """

    return "broad_equity"


def _final_impact_for_chain(chain: list[TransmissionNode], ticker_class: str) -> str:
    """Determine ticker-level direction from terminal chain node."""

    if not chain:
        return "neutral"
    last = chain[-1]
    if last.direction is None:
        return "neutral"
    key_map = {
        "yields": "yields_up" if last.direction == "up" else "yields_down",
        "liquidity": "liquidity_up" if last.direction == "up" else "liquidity_down",
        "oil": "oil_up" if last.direction == "up" else "oil_down",
        "dollar": "dollar_up" if last.direction == "up" else "dollar_down",
    }
    asset = key_map.get(last.node)
    if asset is None:
        return "mixed"
    return _TICKER_IMPACT.get((asset, ticker_class), "neutral")


def build_macro_transmission_chain(
    *,
    ticker: str,
    dominant_narrative: str | None,
    key_events: list[dict[str, Any]] | None,
    event_risk_drivers: list[str] | None,
) -> dict[str, Any] | None:
    """Detect a macro shock and project its first-order chain.

    Returns a dict with ``primary_shock``, ``chain[]``, and
    ``ticker_impact``. ``None`` when no shock matches the simple
    topology table — the report panel will simply not render in that
    case.
    """

    candidates: list[str] = []
    if dominant_narrative:
        candidates.append(str(dominant_narrative))
    for ev in key_events or []:
        for field in ("event_type", "title", "summary"):
            v = ev.get(field) if isinstance(ev, dict) else None
            if v:
                candidates.append(str(v))
    for d in event_risk_drivers or []:
        candidates.append(str(d))

    detected: str | None = None
    detected_evidence: str | None = None
    for text in candidates:
        shock = _detect_shock(text)
        if shock is not None:
            detected = shock
            detected_evidence = text[:200]
            break

    if detected is None and candidates:
        # Cross-candidate fallback: signals often split across
        # event_type ("FOMC") and title ("Powell hawkish"). Combine all
        # candidate strings into a single blob for a second pass.
        combined = " | ".join(candidates)
        shock = _detect_shock(combined)
        if shock is not None:
            detected = shock
            detected_evidence = combined[:200]

    if detected is None:
        return None

    topology = _TRANSMISSION_TOPOLOGY.get(detected) or []
    if not topology:
        return None

    chain: list[TransmissionNode] = [
        TransmissionNode(
            node="shock",
            label=detected.replace("_", " ").title(),
            direction="mixed",
            evidence=detected_evidence,
        )
    ]
    for node_id, label, direction in topology:
        chain.append(
            TransmissionNode(
                node=node_id,
                label=label,
                direction=direction,
                evidence=None,
            )
        )

    ticker_class = _classify_ticker(ticker)
    final_impact = _final_impact_for_chain(chain, ticker_class)

    # Append a terminal node showing ticker impact
    ticker_label = {
        "supportive": f"Supportive For {ticker.upper()}",
        "bearish": f"Bearish For {ticker.upper()}",
        "neutral": f"Neutral For {ticker.upper()}",
        "mixed": f"Mixed Impact On {ticker.upper()}",
    }.get(final_impact, f"Impact On {ticker.upper()}")
    chain.append(
        TransmissionNode(
            node="ticker",
            label=ticker_label,
            direction={
                "supportive": "up",
                "bearish": "down",
                "neutral": "flat",
                "mixed": "mixed",
            }.get(final_impact),
        )
    )

    return {
        "primary_shock": detected,
        "ticker_impact": final_impact,
        "chain": [node.as_dict() for node in chain],
    }
