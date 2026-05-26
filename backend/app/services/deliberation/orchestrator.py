"""Deliberation orchestrator — hybrid analysis + decision council."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from app.core.config import Settings
from app.services.assessment import run_assessment_team
from app.services.deliberation.analysis.adapters import desk_report_to_opinion
from app.services.deliberation.analysis.run_desk_analysis import run_desk_analysis
from app.services.deliberation.context_builder import build_deliberation_context
from app.services.deliberation.council import run_decision_council
from app.services.deliberation.debate.consensus import synthesize_consensus
from app.services.deliberation.debate.round2_cross_critique import run_cross_critique
from app.services.deliberation.debate.round3_revision import run_revision_round
from app.services.deliberation.debate.routing import DebateAssignment
from app.services.deliberation.decision_labels import council_to_dashboard
from app.services.deliberation.evidence_verifier import EvidenceVerifier
from app.services.deliberation.intelligence.package_builder import build_intelligence_package
from app.services.deliberation.llm_clients.registry import ALL_DIL_MODEL_KEYS, get_client_map
from app.services.deliberation.roles import get_active_desks
from app.services.deliberation.schemas import DebateCritique, DeliberationLayer
from app.services.deliberation.scoring.disagreement import build_metrics
from app.services.deliberation.triggers.decision_triggers import evaluate_decision_trigger
from app.services.dil_resilience.registry import get_resilience_gateway

log = structlog.get_logger(__name__)


def _serialize_models(items: dict) -> dict[str, Any]:
    return {k: v.model_dump() if hasattr(v, "model_dump") else v for k, v in items.items()}


class DeliberationOrchestrator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def run(self, report: dict[str, Any], ticker: str) -> DeliberationLayer:
        meta = report.get("_pipeline_meta") or {}
        run_id = meta.get("run_id") or report.get("deliberation_layer", {}).get("run_id")
        started = datetime.now(UTC).isoformat()
        requested_models = list(ALL_DIL_MODEL_KEYS)

        client_map = get_client_map(self._settings)
        if len(client_map) < self._settings.dil_min_models:
            return DeliberationLayer(
                status="skipped",
                run_id=run_id,
                started_at=started,
                completed_at=datetime.now(UTC).isoformat(),
                models_requested=requested_models,
                skip_reason=(
                    f"Insufficient models configured ({len(client_map)} < "
                    f"{self._settings.dil_min_models})"
                ),
            )

        desks = get_active_desks(self._settings)
        desks_requested = [d.key for d in desks]

        context = build_deliberation_context(report, ticker)
        regime_hint = context.regime_context
        log.info(
            "dil.start",
            ticker=ticker,
            desks=desks_requested,
            providers=list(client_map.keys()),
        )

        # Stage 1 — desk analysis (always on)
        desk_reports = await run_desk_analysis(
            desks, client_map, context, regime_hint=regime_hint
        )
        valid_reports = {k: v for k, v in desk_reports.items() if not v.error}
        get_resilience_gateway().metrics.record_desk_batch(
            success=len(valid_reports),
            failed=len(desk_reports) - len(valid_reports),
        )
        if len(valid_reports) < self._settings.dil_min_models:
            return DeliberationLayer(
                status="failed",
                run_id=run_id,
                started_at=started,
                completed_at=datetime.now(UTC).isoformat(),
                models_requested=requested_models,
                models_used=sorted({v.model for v in valid_reports.values()}),
                desks_requested=desks_requested,
                desks_used=list(valid_reports.keys()),
                analysis_layer={"desks": _serialize_models(desk_reports)},
                round1=_serialize_models(
                    {k: desk_report_to_opinion(v) for k, v in desk_reports.items()}
                ),
                error="Too few successful desk analyses",
            )

        # Legacy opinion map for backward-compatible consensus/metrics
        round1 = {k: desk_report_to_opinion(v) for k, v in desk_reports.items()}

        # Stage 2 — decision trigger + intelligence package
        trigger = evaluate_decision_trigger(
            report,
            build_intelligence_package(
                ticker, "", "none", desk_reports, report
            ),
            self._settings,
        )
        intel = build_intelligence_package(
            ticker,
            trigger.question or "Should we enter this Reverse BWB?",
            trigger.trigger,
            desk_reports,
            report,
        )

        # Stage 2a — Reverse BWB Assessment Team (3 LLMs x 4 rounds) owns
        # every card field except ``decision``. Runs only when the
        # trigger asks for council deliberation; otherwise we let the
        # deterministic projector own the card in the dashboard path.
        assessment_layer_dict: dict[str, Any] | None = None
        assessment_triggered = False
        if (
            self._settings.dil_assessment_enabled
            and trigger.should_run_council
        ):
            try:
                assessment_result = await run_assessment_team(
                    intel, client_map, self._settings
                )
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("dil.assessment.failed", error=str(exc))
                assessment_result = None
            if assessment_result is not None:
                assessment_layer_dict = assessment_result.model_dump(mode="json")
                assessment_triggered = True
                if assessment_result.consensus is not None:
                    intel = build_intelligence_package(
                        ticker,
                        intel.question,
                        intel.trigger,
                        desk_reports,
                        report,
                        assessment_consensus=assessment_result.consensus.model_dump(
                            mode="json"
                        ),
                    )

        council_layer_dict: dict[str, Any] | None = None
        council_triggered = False
        mapped_decision: str | None = None

        if (
            self._settings.dil_council_enabled
            and trigger.should_run_council
        ):
            council_result = await run_decision_council(
                intel, client_map, self._settings
            )
            if council_result is not None:
                council_layer_dict = council_result.model_dump(mode="json")
                council_triggered = True
                if council_result.consensus:
                    mapped_decision = council_to_dashboard(
                        council_result.consensus.decision
                    )

        # Legacy desk debate (off by default)
        debate_rounds: list[dict[str, Any]] = []
        parsed_debate: list[dict[str, DebateCritique]] = []
        all_assignments: list[DebateAssignment] = []

        if self._settings.dil_desk_debate_enabled:
            max_rounds = min(self._settings.dil_max_debate_rounds, 2)
            use_routing = self._settings.dil_use_challenge_routing
            use_roles = self._settings.dil_use_role_specialization
            d1: dict[str, DebateCritique] = {}

            if max_rounds >= 1:
                d1, assignments_r1 = await run_cross_critique(
                    desks,
                    client_map,
                    round1,
                    use_routing=use_routing,
                    round_index=1,
                    use_roles=use_roles,
                )
                parsed_debate.append(d1)
                debate_rounds.append(_serialize_models(d1))
                all_assignments.extend(assignments_r1)

            if max_rounds >= 2:
                d2, assignments_r2 = await run_revision_round(
                    desks,
                    client_map,
                    round1,
                    d1,
                    use_routing=use_routing,
                    round_index=2,
                    use_roles=use_roles,
                )
                parsed_debate.append(d2)
                debate_rounds.append(_serialize_models(d2))
                all_assignments.extend(assignments_r2)

        metrics = build_metrics(round1, parsed_debate)
        consensus = synthesize_consensus(round1, parsed_debate, metrics)

        if council_layer_dict and council_layer_dict.get("consensus"):
            c_consensus = council_layer_dict["consensus"]
            consensus.debate_summary = c_consensus.get(
                "debate_summary", consensus.debate_summary
            )
            if c_consensus.get("main_conflict"):
                consensus.main_conflicts = [c_consensus["main_conflict"]]

        log.info(
            "dil.complete",
            consensus=consensus.consensus,
            council_triggered=council_triggered,
            council_decision=(
                council_layer_dict.get("consensus", {}).get("decision")
                if council_layer_dict
                else None
            ),
        )

        models_used = sorted({v.model for v in valid_reports.values()})
        layer = DeliberationLayer(
            status="complete",
            run_id=run_id,
            started_at=started,
            completed_at=datetime.now(UTC).isoformat(),
            models_requested=requested_models,
            models_used=models_used,
            desks_requested=desks_requested,
            desks_used=sorted(valid_reports.keys()),
            round1=_serialize_models(round1),
            debate_rounds=debate_rounds,
            consensus=consensus.model_dump(),
            metrics=metrics.model_dump(),
            analysis_layer={"desks": _serialize_models(desk_reports)},
            intelligence_package=intel.model_dump(mode="json"),
            assessment_layer=assessment_layer_dict,
            assessment_triggered=assessment_triggered,
            council_layer=council_layer_dict,
            council_triggered=council_triggered,
            council_question=trigger.question if council_triggered else None,
            mapped_decision=mapped_decision,
        )
        if all_assignments:
            layer.debate_assignments = [a.to_dict() for a in all_assignments]
        if self._settings.dil_use_evidence_verification:
            try:
                layer.evidence_verification = EvidenceVerifier().verify(round1)
            except Exception as e:  # pragma: no cover
                log.warning("dil.evidence.verify_failed", error=str(e))
        return layer
