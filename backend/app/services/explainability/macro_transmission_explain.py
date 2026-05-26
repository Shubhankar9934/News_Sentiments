"""Macro Transmission explainability block.

Composes the report panel payload from two sources:

* The deterministic chain skeleton produced by
  :mod:`app.services.deliberation.context.macro_transmission` and
  stored on ``deliberation_layer.intelligence_package`` or
  ``deliberation_layer.analysis_layer`` (via macro_desk role_focus).
* The macro_desk's LLM narrative — extracted from its reasoning steps.

Falls back to recomputing the chain directly from the report when the
deliberation layer is absent.
"""

from __future__ import annotations

from typing import Any

from app.services.dashboard.schemas import (
    MacroTransmission,
    MacroTransmissionNode,
)


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _extract_chain_from_dil(
    deliberation_layer: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not deliberation_layer:
        return None
    intel_pkg = _safe_dict(deliberation_layer.get("intelligence_package"))
    desks = _safe_dict(intel_pkg.get("desks"))
    if not desks:
        analysis_layer = _safe_dict(deliberation_layer.get("analysis_layer"))
        desks = _safe_dict(analysis_layer.get("desks"))

    macro_desk = _safe_dict(desks.get("macro_desk"))
    # macro_desk role_focus may carry the chain (best signal); otherwise
    # look for it in the package itself.
    metrics = _safe_dict(macro_desk.get("metrics"))
    chain_block = (
        metrics.get("macro_transmission_chain")
        or intel_pkg.get("macro_transmission_chain")
        or None
    )
    if isinstance(chain_block, dict):
        return chain_block
    return None


def _extract_macro_narrative(
    deliberation_layer: dict[str, Any] | None,
) -> str | None:
    if not deliberation_layer:
        return None
    intel_pkg = _safe_dict(deliberation_layer.get("intelligence_package"))
    desks = _safe_dict(intel_pkg.get("desks"))
    if not desks:
        analysis_layer = _safe_dict(deliberation_layer.get("analysis_layer"))
        desks = _safe_dict(analysis_layer.get("desks"))
    macro_desk = _safe_dict(desks.get("macro_desk"))
    narrative = macro_desk.get("transmission_narrative")
    if isinstance(narrative, str) and narrative.strip():
        return narrative.strip()[:600]
    # Fall back to the last reasoning step's analysis.
    reasoning = macro_desk.get("reasoning_steps") or []
    for step in reversed(reasoning):
        if isinstance(step, dict):
            text = step.get("analysis")
            if isinstance(text, str) and text.strip():
                return text.strip()[:600]
    return None


def build_macro_transmission(
    *,
    ticker: str,
    report: dict[str, Any],
    deliberation_layer: dict[str, Any] | None,
) -> MacroTransmission | None:
    chain_block = _extract_chain_from_dil(deliberation_layer)
    if chain_block is None:
        # Re-derive from report directly so the panel still renders if
        # the DIL layer is missing the chain (older reports / partial
        # runs).
        from app.services.deliberation.context.macro_transmission import (
            build_macro_transmission_chain,
        )

        options_intel = (
            report.get("options_intelligence") if isinstance(report, dict) else None
        )
        evblock = (options_intel or {}).get("event_risk") or {}
        chain_block = build_macro_transmission_chain(
            ticker=ticker,
            dominant_narrative=report.get("dominant_narrative")
            if isinstance(report, dict)
            else None,
            key_events=report.get("key_events") if isinstance(report, dict) else None,
            event_risk_drivers=list(evblock.get("drivers") or []),
        )

    if not chain_block:
        return None

    raw_chain = chain_block.get("chain") or []
    nodes: list[MacroTransmissionNode] = []
    for item in raw_chain:
        if not isinstance(item, dict):
            continue
        try:
            nodes.append(MacroTransmissionNode.model_validate(item))
        except Exception:
            continue

    if not nodes:
        return None

    narrative = _extract_macro_narrative(deliberation_layer)

    return MacroTransmission(
        chain=nodes,
        narrative=narrative,
        primary_shock=chain_block.get("primary_shock"),
        ticker_impact=chain_block.get("ticker_impact"),
    )
