"""Deliberation orchestrator — coordinates rounds and consensus."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from app.core.config import Settings
from app.services.deliberation.context_builder import build_deliberation_context
from app.services.deliberation.debate.consensus import synthesize_consensus
from app.services.deliberation.debate.round1_independent import run_independent_round
from app.services.deliberation.debate.round2_cross_critique import run_cross_critique
from app.services.deliberation.debate.round3_revision import run_revision_round
from app.services.deliberation.debate.routing import DebateAssignment
from app.services.deliberation.evidence_verifier import EvidenceVerifier
from app.services.deliberation.llm_clients.registry import ALL_DIL_MODEL_KEYS, get_enabled_clients
from app.services.deliberation.schemas import DebateCritique, DeliberationLayer
from app.services.deliberation.scoring.disagreement import build_metrics

log = structlog.get_logger(__name__)


def _serialize_round1(round1: dict) -> dict[str, Any]:
    return {k: v.model_dump() if hasattr(v, "model_dump") else v for k, v in round1.items()}


def _serialize_debate(rd: dict) -> dict[str, Any]:
    return {k: v.model_dump() if hasattr(v, "model_dump") else v for k, v in rd.items()}


class DeliberationOrchestrator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def run(self, report: dict[str, Any], ticker: str) -> DeliberationLayer:
        meta = report.get("_pipeline_meta") or {}
        run_id = meta.get("run_id") or report.get("deliberation_layer", {}).get("run_id")
        started = datetime.now(UTC).isoformat()
        requested = list(ALL_DIL_MODEL_KEYS)

        clients = get_enabled_clients(self._settings)
        if len(clients) < self._settings.dil_min_models:
            return DeliberationLayer(
                status="skipped",
                run_id=run_id,
                started_at=started,
                completed_at=datetime.now(UTC).isoformat(),
                models_requested=requested,
                skip_reason=(
                    f"Insufficient models configured ({len(clients)} < "
                    f"{self._settings.dil_min_models})"
                ),
            )

        context = build_deliberation_context(report, ticker)
        log.info("dil.start", ticker=ticker, models=[c.model_key for c in clients])

        round1 = await run_independent_round(clients, context)
        valid_round1 = {k: v for k, v in round1.items() if not v.error}
        if len(valid_round1) < self._settings.dil_min_models:
            return DeliberationLayer(
                status="failed",
                run_id=run_id,
                started_at=started,
                completed_at=datetime.now(UTC).isoformat(),
                models_requested=requested,
                models_used=list(valid_round1.keys()),
                round1=_serialize_round1(round1),
                error="Too few successful independent opinions",
            )

        debate_rounds: list[dict[str, Any]] = []
        parsed_debate: list[dict[str, DebateCritique]] = []
        max_rounds = min(self._settings.dil_max_debate_rounds, 2)
        d1: dict[str, DebateCritique] = {}
        all_assignments: list[DebateAssignment] = []
        use_routing = self._settings.dil_use_challenge_routing

        if max_rounds >= 1:
            d1, assignments_r1 = await run_cross_critique(
                clients, round1, use_routing=use_routing, round_index=1
            )
            parsed_debate.append(d1)
            debate_rounds.append(_serialize_debate(d1))
            all_assignments.extend(assignments_r1)
            log.info(
                "dil.debate.round",
                round=1,
                routed=use_routing,
                assignment_count=len(assignments_r1),
            )

        if max_rounds >= 2:
            d2, assignments_r2 = await run_revision_round(
                clients,
                round1,
                d1,
                use_routing=use_routing,
                round_index=2,
            )
            parsed_debate.append(d2)
            debate_rounds.append(_serialize_debate(d2))
            all_assignments.extend(assignments_r2)
            log.info(
                "dil.debate.round",
                round=2,
                routed=use_routing,
                assignment_count=len(assignments_r2),
            )

        metrics = build_metrics(round1, parsed_debate)

        consensus = synthesize_consensus(round1, parsed_debate, metrics)
        log.info("dil.consensus", consensus=consensus.consensus, agreement=consensus.agreement_score)

        # models_used reflects who *successfully* contributed valid round-1
        # output, not just who we configured. Down-stream calibration depends
        # on this being accurate.
        models_used = sorted(valid_round1.keys())
        layer = DeliberationLayer(
            status="complete",
            run_id=run_id,
            started_at=started,
            completed_at=datetime.now(UTC).isoformat(),
            models_requested=requested,
            models_used=models_used,
            round1=_serialize_round1(round1),
            debate_rounds=debate_rounds,
            consensus=consensus.model_dump(),
            metrics=metrics.model_dump(),
        )
        if all_assignments:
            layer.debate_assignments = [a.to_dict() for a in all_assignments]
        if self._settings.dil_use_evidence_verification:
            try:
                layer.evidence_verification = EvidenceVerifier().verify(round1)
            except Exception as e:  # pragma: no cover — verifier must never break the run
                log.warning("dil.evidence.verify_failed", error=str(e))
        return layer
