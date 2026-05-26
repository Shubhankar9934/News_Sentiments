"""Desk registry — roles decoupled from LLM providers.

Each desk owns a unique analytical responsibility. Provider assignment
(primary + ordered fallbacks) is configurable via settings; consensus and
debate routing key off ``desk.key``, not the provider that answered.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

from app.core.config import Settings
from app.services.dil_resilience.routing import RoutingConfig
from app.services.deliberation.schemas import ModelKey

RoleKey = Literal[
    "macro_desk",
    "fundamental_desk",
    "options_desk",
    "risk_desk",
    "devils_advocate_desk",
    "technical_desk",
    "news_desk",
    "earnings_desk",
    "event_risk_desk",
    "flow_desk",
    "liquidity_desk",
    "regime_desk",
    "quant_desk",
    "reverse_bwb_structure_desk",
]

ALL_MODEL_KEYS: tuple[ModelKey, ...] = ("gpt", "claude", "gemini", "deepseek", "groq")

CORE_DESK_KEYS: tuple[str, ...] = (
    "macro_desk",
    "fundamental_desk",
    "options_desk",
    "risk_desk",
    "devils_advocate_desk",
)

ALL_DESK_KEYS: tuple[str, ...] = CORE_DESK_KEYS + (
    "technical_desk",
    "news_desk",
    "earnings_desk",
    "event_risk_desk",
    "flow_desk",
    "liquidity_desk",
    "regime_desk",
    "quant_desk",
    "reverse_bwb_structure_desk",
)

DESK_LABELS: dict[str, str] = {
    "macro_desk": "Macro Desk",
    "fundamental_desk": "Fundamental Desk",
    "options_desk": "Options Desk",
    "risk_desk": "Risk Desk",
    "devils_advocate_desk": "Devil's Advocate Desk",
    "technical_desk": "Technical Desk",
    "news_desk": "News Intelligence Desk",
    "earnings_desk": "Earnings Desk",
    "event_risk_desk": "Event Risk Desk",
    "flow_desk": "Flow Desk",
    "liquidity_desk": "Liquidity Desk",
    "regime_desk": "Regime Desk",
    "quant_desk": "Quant Desk",
    "reverse_bwb_structure_desk": "Reverse BWB Structure Desk",
}

# Legacy provider→desk mapping (primary assignments unchanged).
DESK_ROLES: dict[str, dict[str, str]] = {
    "gpt": {"key": "macro_desk", "label": "Macro Desk"},
    "claude": {"key": "fundamental_desk", "label": "Fundamental Desk"},
    "groq": {"key": "options_desk", "label": "Options Desk"},
    "deepseek": {"key": "risk_desk", "label": "Risk Desk"},
    "gemini": {"key": "devils_advocate_desk", "label": "Devil's Advocate Desk"},
}

DEFAULT_ROLE: dict[str, str] = {"key": "macro_desk", "label": "Macro Desk"}

ROLE_STEP_TITLES: dict[str, list[str]] = {
    "macro_desk": [
        "Rate & Liquidity",
        "Sector Breadth",
        "Risk-On / Risk-Off",
        "Macro Catalysts",
        "Macro Assessment",
    ],
    "fundamental_desk": [
        "Earnings & Guidance",
        "Segment Growth",
        "Margin Trajectory",
        "Valuation Multiple",
        "Fundamental Assessment",
    ],
    "options_desk": [
        "Implied vs Realized Vol",
        "Expected Move & Pin Risk",
        "Dealer Positioning Proxy",
        "Structure Suitability",
        "Options Assessment",
    ],
    "risk_desk": [
        "Downside Scenarios",
        "Invalidators",
        "Tail Risks",
        "Position Sizing Guard",
        "Risk Assessment",
    ],
    "devils_advocate_desk": [
        "Consensus Centroid",
        "Bear Case",
        "Hidden Assumptions",
        "Stress Test",
        "Contrarian Assessment",
    ],
    "technical_desk": [
        "Trend Structure",
        "Support & Resistance",
        "Momentum Indicators",
        "Volatility & ATR",
        "Technical Assessment",
    ],
    "news_desk": [
        "Headline Sentiment",
        "News Momentum",
        "Narrative Shifts",
        "Source Quality",
        "News Assessment",
    ],
    "earnings_desk": [
        "Earnings Calendar",
        "Guidance Trajectory",
        "Analyst Revisions",
        "Post-Earnings Risk",
        "Earnings Assessment",
    ],
    "event_risk_desk": [
        "Scheduled Events",
        "Binary Risk Windows",
        "Vol Crush Risk",
        "Event Overlap",
        "Event Risk Assessment",
    ],
    "flow_desk": [
        "Unusual Activity",
        "Call vs Put Skew",
        "Volume Anomalies",
        "Dark-Pool Proxy",
        "Flow Assessment",
    ],
    "liquidity_desk": [
        "Spread Quality",
        "Volume Depth",
        "Open Interest",
        "Execution Risk",
        "Liquidity Assessment",
    ],
    "regime_desk": [
        "Regime Classification",
        "Volatility State",
        "Macro Week Overlay",
        "Historical Analogs",
        "Regime Assessment",
    ],
    "quant_desk": [
        "Move Probabilities",
        "Sigma Distances",
        "Expected Value",
        "Historical Analog Stats",
        "Quant Assessment",
    ],
    "reverse_bwb_structure_desk": [
        "Body Placement",
        "Wing Width Adequacy",
        "Credit Efficiency",
        "Probability of Touch",
        "Structure Verdict",
    ],
}

# Primary provider per desk (unchanged for core 5).
_DESK_PRIMARIES: dict[str, ModelKey] = {
    "macro_desk": "gpt",
    "fundamental_desk": "claude",
    "options_desk": "groq",
    "risk_desk": "deepseek",
    "devils_advocate_desk": "gemini",
    "technical_desk": "gemini",
    "news_desk": "gemini",
    "earnings_desk": "claude",
    "event_risk_desk": "groq",
    "flow_desk": "gpt",
    "liquidity_desk": "deepseek",
    "regime_desk": "gpt",
    "quant_desk": "deepseek",
    "reverse_bwb_structure_desk": "deepseek",
}


def _default_fallbacks(primary: ModelKey) -> tuple[ModelKey, ...]:
    return default_provider_fallbacks(primary)


def default_provider_fallbacks(primary: ModelKey) -> tuple[ModelKey, ...]:
    """Ordered provider fallbacks. Groq daily caps → prefer DeepSeek first."""
    if primary == "groq":
        return ("deepseek", "gpt", "claude", "gemini")
    return tuple(m for m in ALL_MODEL_KEYS if m != primary)


@dataclass(frozen=True)
class DeskDefinition:
    key: str
    label: str
    primary: ModelKey
    fallbacks: tuple[ModelKey, ...]
    enabled: bool = True

    @property
    def provider_chain(self) -> tuple[ModelKey, ...]:
        return (self.primary, *self.fallbacks)


def build_desk_registry(settings: Settings) -> dict[str, DeskDefinition]:
    fallback_overrides = _parse_desk_fallback_env(settings)
    routing = RoutingConfig(settings)
    registry: dict[str, DeskDefinition] = {}
    for key in ALL_DESK_KEYS:
        default_primary = _DESK_PRIMARIES[key]
        default_fallbacks = fallback_overrides.get(key, _default_fallbacks(default_primary))
        primary, fallbacks = routing.resolve_desk_chain(
            key, default_primary, default_fallbacks
        )
        registry[key] = DeskDefinition(
            key=key,
            label=DESK_LABELS[key],
            primary=primary,  # type: ignore[arg-type]
            fallbacks=fallbacks,  # type: ignore[arg-type]
        )
    return registry


def _parse_desk_fallback_env(settings: Settings) -> dict[str, tuple[ModelKey, ...]]:
    """Read per-desk fallback overrides from ``settings.dil_desk_fallbacks``."""
    overrides: dict[str, tuple[ModelKey, ...]] = {}
    raw_map = getattr(settings, "dil_desk_fallbacks", {}) or {}
    for desk_key, raw in raw_map.items():
        if desk_key not in ALL_DESK_KEYS or not raw:
            continue
        parts = [p.strip().lower() for p in str(raw).split(",") if p.strip()]
        valid = tuple(p for p in parts if p in ALL_MODEL_KEYS)  # type: ignore[misc]
        if valid:
            overrides[desk_key] = valid  # type: ignore[assignment]
    return overrides


def get_active_desks(settings: Settings) -> list[DeskDefinition]:
    registry = build_desk_registry(settings)
    active_keys = settings.dil_active_desk_set
    if not active_keys:
        active_keys = set(ALL_DESK_KEYS)
    return [registry[k] for k in ALL_DESK_KEYS if k in active_keys and k in registry]


def role_for(model_key: str) -> dict[str, str]:
    """Legacy: return desk for a provider's old permanent chair."""
    return DESK_ROLES.get(model_key.lower(), DEFAULT_ROLE)


def role_step_titles(role_key: str) -> list[str]:
    return ROLE_STEP_TITLES.get(role_key, ROLE_STEP_TITLES["macro_desk"])


def desk_label(role_key: str) -> str:
    return DESK_LABELS.get(role_key, role_key.replace("_", " ").title())


def context_view_for_role(
    context: dict[str, Any],
    role_key: str,
    *,
    regime_hint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a role-tilted dict-view of the deliberation context."""
    base = dict(context)
    if role_key == "macro_desk":
        focus = {
            "market_context": context.get("market_context") or {},
            "macro_articles": _filter_evidence_by_event(
                context.get("article_evidence") or [], {"Macro", "Regulation"}
            ),
            # Phase 6: deterministic transmission chain skeleton — gives
            # the macro desk a structured causal map to narrate.
            "macro_transmission_chain": context.get("macro_transmission_chain") or {},
        }
    elif role_key == "fundamental_desk":
        focus = {
            "narrative": context.get("narrative") or {},
            "key_events": context.get("key_events") or [],
            "earnings_articles": _filter_evidence_by_event(
                context.get("article_evidence") or [],
                {"Earnings", "Guidance", "Partnership", "Product"},
            ),
        }
    elif role_key == "options_desk":
        focus = {
            "options_intelligence": context.get("options_intelligence") or {},
            "market_context": context.get("market_context") or {},
            "vol_regime": (context.get("market_context") or {}).get("volatility_regime"),
        }
    elif role_key == "risk_desk":
        focus = {
            "key_events": context.get("key_events") or [],
            "top_impact_events": context.get("top_impact_events") or [],
            "negative_evidence": _filter_evidence_by_sentiment(
                context.get("article_evidence") or [], "bearish"
            ),
        }
    elif role_key == "devils_advocate_desk":
        focus = {
            "panel_centroid_hint": (
                "Argue against whichever stance the panel is gravitating toward."
            ),
            "narrative": context.get("narrative") or {},
            "sentiment": context.get("sentiment") or {},
        }
    elif role_key == "technical_desk":
        focus = {
            "technical_context": context.get("technical_context") or {},
            "market_context": context.get("market_context") or {},
        }
    elif role_key == "news_desk":
        focus = {
            "article_evidence": (context.get("article_evidence") or [])[:12],
            "news_momentum": context.get("news_momentum") or {},
            "sentiment": context.get("sentiment") or {},
        }
    elif role_key == "earnings_desk":
        focus = {
            "earnings_articles": _filter_evidence_by_event(
                context.get("article_evidence") or [],
                {"Earnings", "Guidance"},
            ),
            "key_events": [
                e
                for e in (context.get("key_events") or [])
                if "earn" in str(e.get("event_type", "")).lower()
                or "guidance" in str(e.get("event_type", "")).lower()
            ],
            "options_intelligence": {
                "event_risk": (context.get("options_intelligence") or {}).get("event_risk"),
            },
        }
    elif role_key == "event_risk_desk":
        oi = context.get("options_intelligence") or {}
        focus = {
            "event_risk": oi.get("event_risk") or {},
            "key_events": context.get("key_events") or [],
            "top_impact_events": context.get("top_impact_events") or [],
        }
    elif role_key == "flow_desk":
        focus = {
            "flow_context": context.get("flow_context") or {},
            "options_intelligence": context.get("options_intelligence") or {},
        }
    elif role_key == "liquidity_desk":
        focus = {
            "liquidity_context": context.get("liquidity_context") or {},
            "options_intelligence": context.get("options_intelligence") or {},
        }
    elif role_key == "regime_desk":
        focus = {
            "regime_context": context.get("regime_context") or {},
            "historical_analogs": context.get("historical_analogs") or [],
            "market_context": context.get("market_context") or {},
        }
    elif role_key == "quant_desk":
        oi = context.get("options_intelligence") or {}
        focus = {
            "move_probabilities": oi.get("move_probabilities") or {},
            "expected_range": oi.get("expected_range") or {},
            "credit_safety": oi.get("credit_safety") or {},
            "historical_analogs": context.get("historical_analogs") or [],
            "flow_context": context.get("flow_context") or {},
        }
    elif role_key == "reverse_bwb_structure_desk":
        oi = context.get("options_intelligence") or {}
        focus = {
            "structure_geometry": oi.get("structure_geometry") or {},
            "position_risk": oi.get("position_risk") or {},
            "body_danger": oi.get("body_danger") or {},
            "pin_risk": oi.get("pin_risk") or {},
            "reverse_bwb": oi.get("reverse_bwb") or {},
            "move_probabilities": oi.get("move_probabilities") or {},
            "expected_range": oi.get("expected_range") or {},
            "credit_safety": oi.get("credit_safety") or {},
        }
    else:
        focus = {}

    if regime_hint and role_key != "regime_desk":
        focus["regime_hint"] = regime_hint

    base["role_focus"] = focus
    return base


def _filter_evidence_by_event(
    evidence: Iterable[dict[str, Any]], event_types: Iterable[str]
) -> list[dict[str, Any]]:
    targets = {e.lower() for e in event_types}
    out: list[dict[str, Any]] = []
    for row in evidence:
        et = (row.get("event_type") or "").lower()
        if et in targets:
            out.append(row)
        if len(out) >= 8:
            break
    return out


def _filter_evidence_by_sentiment(
    evidence: Iterable[dict[str, Any]], sentiment: str
) -> list[dict[str, Any]]:
    target = sentiment.lower()
    out: list[dict[str, Any]] = []
    for row in evidence:
        if (row.get("sentiment_label") or "").lower().startswith(target[:4]):
            out.append(row)
        if len(out) >= 8:
            break
    return out
