"""Confidence Calibration explanation for the Open Full Report.

Pure read-side composition. Pulls signals that already exist on the
deliberation layer (desk-layer ``calibration``, metrics
``contradiction_density``, council ``consensus.confidence``) and
composes the user-facing 5-row breakdown the report renders.

The final ``Low/Medium/High`` bucket mirrors the card's ``confidence``
field byte-for-byte — this builder never recomputes the bucket. Only
the percentage and the per-row drivers are derived here.
"""

from __future__ import annotations

from typing import Any

from app.services.dashboard.schemas import (
    ConfidenceCalibration,
    ConfidenceCalibrationRow,
    ConfidenceLevel,
    ReverseBwbSummary,
)


def _pct(x: float | None) -> float | None:
    if x is None:
        return None
    return round(max(0.0, min(1.0, float(x))) * 100.0, 1)


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _bucket_to_pct(bucket: str) -> float:
    return {"Low": 35.0, "Medium": 60.0, "High": 80.0}.get(bucket, 55.0)


def build_confidence_calibration(
    *,
    ticker: str,  # noqa: ARG001 - kept for assembler symmetry
    deliberation_layer: dict[str, Any] | None,
    summary: ReverseBwbSummary | None,
) -> ConfidenceCalibration | None:
    """Compose the 5-row confidence-calibration breakdown.

    Returns ``None`` if no deliberation layer is present — the card
    confidence bucket alone is not enough to explain "why".
    """

    if not deliberation_layer:
        return None

    consensus_block = _safe_dict(deliberation_layer.get("consensus"))
    calibration = _safe_dict(consensus_block.get("calibration"))
    metrics = _safe_dict(deliberation_layer.get("metrics"))
    council = _safe_dict(deliberation_layer.get("council_layer"))
    council_consensus = _safe_dict(council.get("consensus"))

    raw_desk = calibration.get("confidence_aggregate")
    cross_agent = calibration.get("consensus_strength")
    evidence = calibration.get("evidence_quality")
    contradiction = metrics.get("contradiction_density")
    council_conf = council_consensus.get("confidence")

    raw_pct = _pct(raw_desk)
    cross_pct = _pct(cross_agent)
    evidence_pct = _pct(evidence)
    contradiction_pct = _pct(contradiction)
    council_pct = _pct(council_conf) if isinstance(council_conf, (int, float)) else None

    if raw_pct is None and cross_pct is None and council_pct is None:
        return None

    raw_row = ConfidenceCalibrationRow(
        label="Raw Desk Confidence",
        value=raw_pct,
        explanation=(
            f"Average analytical-confidence across desks: {raw_pct:.1f}%."
            if raw_pct is not None
            else "Desk-level calibration unavailable for this run."
        ),
    )
    cross_row = ConfidenceCalibrationRow(
        label="Cross-Agent Agreement",
        value=cross_pct,
        explanation=(
            f"Inter-desk agreement strength: {cross_pct:.1f}% (1 - stance entropy)."
            if cross_pct is not None
            else "Cross-agent agreement unavailable."
        ),
    )
    evidence_row = ConfidenceCalibrationRow(
        label="Evidence Overlap",
        value=evidence_pct,
        explanation=(
            f"Reasoning + evidence overlap across desks: {evidence_pct:.1f}%."
            if evidence_pct is not None
            else "Evidence overlap unavailable."
        ),
    )

    # Contradiction penalty is the *negative* signal contribution.
    penalty_value = None
    if contradiction_pct is not None:
        penalty_value = round(-1.0 * contradiction_pct * 0.5, 1)
    penalty_row = ConfidenceCalibrationRow(
        label="Contradiction Penalty",
        value=penalty_value,
        explanation=(
            f"Contradiction density {contradiction_pct:.1f}% → {penalty_value:.1f}% deduction "
            "from raw confidence."
            if contradiction_pct is not None and penalty_value is not None
            else "No measurable contradictions detected across desks."
        ),
    )

    council_row: ConfidenceCalibrationRow | None = None
    if council_pct is not None:
        council_row = ConfidenceCalibrationRow(
            label="Council Confidence",
            value=council_pct,
            explanation=(
                f"Mean confidence across the {len(_safe_dict(council.get('round1')))}-member "
                f"council after revision: {council_pct:.1f}%."
            ),
        )

    # Composite final pct: blend of raw + cross + evidence with penalty,
    # then weighted average with council confidence when present.
    components = [
        v
        for v in [raw_pct, cross_pct, evidence_pct]
        if isinstance(v, (int, float))
    ]
    composite = sum(components) / len(components) if components else 60.0
    composite += penalty_value or 0.0
    if council_pct is not None:
        composite = 0.6 * council_pct + 0.4 * composite
    composite = max(0.0, min(100.0, composite))

    # Card bucket is authoritative for the *bucket* label so the report
    # never disagrees with the card.
    card_bucket: ConfidenceLevel
    if summary is not None:
        card_bucket = summary.confidence
    else:
        if composite >= 70.0:
            card_bucket = "High"
        elif composite >= 50.0:
            card_bucket = "Medium"
        else:
            card_bucket = "Low"

    # Snap the final pct to the bucket range for visual coherence.
    bucket_anchor = _bucket_to_pct(card_bucket)
    final_pct = round(0.6 * composite + 0.4 * bucket_anchor, 1)

    return ConfidenceCalibration(
        raw_desk_confidence=raw_row,
        cross_agent_agreement=cross_row,
        evidence_overlap=evidence_row,
        contradiction_penalty=penalty_row,
        council_confidence=council_row,
        final_confidence_pct=final_pct,
        final_confidence_bucket=card_bucket,
    )
