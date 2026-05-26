"""Structure-analysis explainability block.

Reads the deterministic ``options_intelligence.structure_geometry``
block produced by :mod:`app.services.options.structure_geometry` and
the optional ``reverse_bwb_structure_desk`` LLM narrative produced by
Phase 4b, and composes the report panel payload.
"""

from __future__ import annotations

from typing import Any

from app.services.dashboard.schemas import (
    StructureAnalysisExplain,
    StructureGeometry,
)


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def build_structure_analysis(
    *,
    ticker: str,  # noqa: ARG001
    options_intel: dict[str, Any] | None,
    deliberation_layer: dict[str, Any] | None,
) -> StructureAnalysisExplain | None:
    if not options_intel:
        return None

    geometry_block = options_intel.get("structure_geometry")
    if not geometry_block:
        return None

    try:
        geometry = StructureGeometry.model_validate(geometry_block)
    except Exception:
        return None

    desk_narrative = None
    desk_role = None
    desk_model = None
    if deliberation_layer:
        intel_pkg = _safe_dict(deliberation_layer.get("intelligence_package"))
        desks = _safe_dict(intel_pkg.get("desks"))
        # Also fall back to analysis_layer.desks for compatibility.
        if not desks:
            analysis_layer = _safe_dict(deliberation_layer.get("analysis_layer"))
            desks = _safe_dict(analysis_layer.get("desks"))

        desk = _safe_dict(desks.get("reverse_bwb_structure_desk"))
        if desk:
            desk_role = desk.get("role_key")
            desk_model = desk.get("model")
            findings = desk.get("key_findings") or []
            reasoning = desk.get("reasoning_steps") or []
            # Prefer a top-level "narrative" if present, else stitch
            # findings + first reasoning step analysis.
            parts: list[str] = []
            if findings:
                parts.append(" ".join(str(f) for f in findings[:2]))
            if reasoning:
                first = reasoning[0] if isinstance(reasoning[0], dict) else {}
                analysis_text = first.get("analysis")
                if analysis_text:
                    parts.append(str(analysis_text))
            if parts:
                desk_narrative = " ".join(parts).strip()[:2000]

    return StructureAnalysisExplain(
        geometry=geometry,
        desk_narrative=desk_narrative,
        desk_role_key=desk_role,
        desk_model=desk_model,
    )
