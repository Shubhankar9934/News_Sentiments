"""Read/write deliberation data on research reports."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.tables import DeliberationRunModel, ResearchReportModel


_OUTCOME_HORIZON_DAYS = 3  # default 1-3d outlook horizon


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError):
        return None


def _extract_calibration_lineage(layer: dict[str, Any]) -> dict[str, Any]:
    """Pull the lineage columns from a complete deliberation layer.

    Resilient to legacy layers that pre-date PR1's calibration block — any
    missing field maps to ``None`` so the columns simply stay NULL.
    """
    consensus = layer.get("consensus") or {}
    metrics = layer.get("metrics") or {}
    calibration = consensus.get("calibration") or {}
    structured_risks = consensus.get("structured_risks") or []
    primary_risks: list[dict[str, Any]] = []
    for r in structured_risks[:5]:
        if isinstance(r, dict):
            primary_risks.append(
                {
                    "headline": r.get("headline"),
                    "support_count": r.get("support_count"),
                    "severity": r.get("severity"),
                    "topic": r.get("topic"),
                }
            )
    started_raw = layer.get("started_at")
    outcome_window_end: datetime | None = None
    if started_raw:
        try:
            started = datetime.fromisoformat(started_raw.replace("Z", "+00:00"))
            outcome_window_end = started + timedelta(days=_OUTCOME_HORIZON_DAYS)
        except ValueError:
            outcome_window_end = None
    return {
        "consensus_stance": consensus.get("consensus"),
        "reconciled_label": consensus.get("reconciled_label"),
        "consensus_confidence": _to_decimal(calibration.get("confidence_aggregate")),
        "directional_conviction": _to_decimal(calibration.get("directional_conviction")),
        "consensus_strength": _to_decimal(calibration.get("consensus_strength")),
        "agreement_score": _to_decimal(consensus.get("agreement_score")),
        "divergence": _to_decimal(metrics.get("model_divergence")),
        "contradiction_density": _to_decimal(metrics.get("contradiction_density")),
        "uncertainty": (calibration.get("uncertainty") or consensus.get("uncertainty")),
        "primary_risks": primary_risks or None,
        "outcome_window_end": outcome_window_end,
    }


class DeliberationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_report_by_id(self, report_id: uuid.UUID) -> ResearchReportModel | None:
        result = await self._session.execute(
            select(ResearchReportModel).where(ResearchReportModel.id == report_id)
        )
        return result.scalar_one_or_none()

    async def update_deliberation_layer(
        self,
        report_id: uuid.UUID,
        layer: dict[str, Any],
        *,
        ticker: str | None = None,
    ) -> bool:
        row = await self.get_report_by_id(report_id)
        if not row:
            return False
        report_json = dict(row.report_json or {})
        report_json["deliberation_layer"] = layer
        await self._session.execute(
            update(ResearchReportModel)
            .where(ResearchReportModel.id == report_id)
            .values(report_json=report_json)
        )
        await self._session.commit()
        return True

    async def persist_deliberation_run(
        self,
        report_id: uuid.UUID,
        ticker: str,
        run_id: str | None,
        status: str,
        models_used: list[str],
        layer_json: dict[str, Any],
    ) -> None:
        existing = await self._session.execute(
            select(DeliberationRunModel).where(DeliberationRunModel.report_id == report_id)
        )
        row = existing.scalar_one_or_none()
        now = datetime.now(UTC)
        is_terminal = status in ("complete", "failed", "skipped")
        lineage = _extract_calibration_lineage(layer_json) if status == "complete" else {}
        if row:
            row.status = status
            row.models_used = models_used
            row.layer_json = layer_json
            row.completed_at = now if is_terminal else None
            for col, value in lineage.items():
                setattr(row, col, value)
        else:
            self._session.add(
                DeliberationRunModel(
                    report_id=report_id,
                    ticker=ticker,
                    run_id=run_id,
                    status=status,
                    models_used=models_used,
                    layer_json=layer_json,
                    completed_at=now if is_terminal else None,
                    **lineage,
                )
            )
        await self._session.commit()
