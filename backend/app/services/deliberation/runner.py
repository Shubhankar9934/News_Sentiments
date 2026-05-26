"""Run deliberation inline (uvicorn) or via Celery worker."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog

from app.core.config import Settings, get_settings

log = structlog.get_logger(__name__)

_in_flight: set[str] = set()
_kick_attempted: set[str] = set()


async def execute_deliberation(report_id: str) -> dict[str, Any]:
    """Run full DIL pipeline and persist results on the research report."""
    if report_id in _in_flight:
        return {"status": "running", "report_id": report_id}

    _in_flight.add(report_id)
    try:
        from app.db.repositories.deliberation_repository import DeliberationRepository
        from app.db.session import SessionLocal
        from app.services.deliberation.orchestrator import DeliberationOrchestrator

        settings = get_settings()
        if not settings.dil_enabled:
            return {"status": "skipped", "reason": "DIL_ENABLED=false"}

        rid = uuid.UUID(report_id)
        async with SessionLocal() as session:
            repo = DeliberationRepository(session)
            row = await repo.get_report_by_id(rid)
            if not row:
                log.error("dil.report_not_found", report_id=report_id)
                return {"status": "failed", "error": "report not found"}

            report = dict(row.report_json or {})
            ticker = row.ticker
            layer = dict(report.get("deliberation_layer") or {})
            if layer.get("status") in ("complete", "failed", "skipped"):
                return {**layer, "report_id": report_id}

            layer["status"] = "running"
            await repo.update_deliberation_layer(rid, layer, ticker=ticker)

            try:
                orchestrator = DeliberationOrchestrator(settings)
                result = await orchestrator.run(report, ticker)
                layer_dict = result.to_dict()
                await repo.update_deliberation_layer(rid, layer_dict, ticker=ticker)
                try:
                    await repo.persist_deliberation_run(
                        rid,
                        ticker,
                        layer_dict.get("run_id"),
                        layer_dict.get("status", "complete"),
                        layer_dict.get("models_used") or [],
                        layer_dict,
                    )
                except Exception as persist_err:
                    await session.rollback()
                    log.warning(
                        "dil.persist_run_failed",
                        report_id=report_id,
                        error=str(persist_err),
                    )

                # Stage-2 executive-summary refresh: now that DIL consensus
                # exists, recompute outlook/confidence/risk so the grid card
                # upgrades from v1 to v2 metrics.
                summary_v2: dict[str, Any] | None = None
                if layer_dict.get("status") == "complete":
                    try:
                        from app.services.summary import extract_executive_summary

                        merged = {**report, "deliberation_layer": layer_dict}
                        summary_v2 = extract_executive_summary(merged).model_dump()
                        await repo.update_executive_summary(rid, summary_v2)
                    except Exception as summary_err:
                        log.warning(
                            "dil.executive_summary_refresh_failed",
                            report_id=report_id,
                            error=str(summary_err),
                        )

                    council_layer = layer_dict.get("council_layer") or {}
                    council_consensus = council_layer.get("consensus") or {}
                    mapped = layer_dict.get("mapped_decision")
                    if mapped and council_consensus.get("decision"):
                        try:
                            from app.db.repositories.dashboard_repository import (
                                DashboardRepository,
                            )

                            dash_repo = DashboardRepository(session)
                            await dash_repo.patch_reverse_bwb_decision(
                                ticker,
                                mapped,
                                council_decision=council_consensus.get("decision"),
                            )
                        except Exception as patch_err:
                            log.warning(
                                "dil.dashboard_patch_failed",
                                report_id=report_id,
                                error=str(patch_err),
                            )

                from redis.asyncio import Redis

                from app.services.cache.redis_cache import RedisCache

                redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
                try:
                    cache = RedisCache(redis_client)
                    cache_payload: dict[str, Any] = {
                        **report,
                        "deliberation_layer": layer_dict,
                    }
                    if summary_v2 is not None:
                        cache_payload["executive_summary"] = summary_v2
                    await cache.set_json(
                        f"research:last:{ticker}",
                        cache_payload,
                        ttl_seconds=120,
                    )
                except Exception:
                    pass
                finally:
                    await redis_client.aclose()

                log.info("dil.complete", report_id=report_id, status=layer_dict.get("status"))
                return layer_dict
            except Exception as e:
                log.exception("dil.failed", report_id=report_id)
                await session.rollback()
                failed = {
                    **layer,
                    "status": "failed",
                    "error": str(e),
                    "completed_at": datetime.now(UTC).isoformat(),
                }
                try:
                    await repo.update_deliberation_layer(rid, failed, ticker=ticker)
                except Exception:
                    log.exception("dil.failed_status_persist", report_id=report_id)
                return failed
    finally:
        _in_flight.discard(report_id)


def schedule_deliberation(
    report_id: str,
    settings: Settings | None = None,
    *,
    prefer_celery: bool | None = None,
) -> None:
    """Enqueue deliberation on Celery or run as a background asyncio task."""
    settings = settings or get_settings()
    if not settings.dil_enabled:
        return

    use_celery = settings.dil_use_celery if prefer_celery is None else prefer_celery
    if use_celery:
        try:
            from app.workers.tasks.deliberation import run_deliberation_task

            run_deliberation_task.delay(report_id)
            log.info("dil.enqueued", report_id=report_id, transport="celery")
            return
        except Exception as e:
            log.warning("dil.enqueue_failed", report_id=report_id, error=str(e))

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        log.warning("dil.no_event_loop", report_id=report_id)
        return

    loop.create_task(execute_deliberation(report_id))
    log.info("dil.enqueued", report_id=report_id, transport="inline")


def schedule_deliberation_if_stale(
    report_id: str,
    layer: dict[str, Any],
    settings: Settings | None = None,
) -> None:
    """Re-kick deliberation when Celery never picked up a pending job (local dev)."""
    settings = settings or get_settings()
    if not settings.dil_enabled:
        return

    status = layer.get("status")
    if status != "pending":
        return
    if report_id in _in_flight or report_id in _kick_attempted:
        return

    started_raw = layer.get("started_at")
    stale_seconds = 15
    if started_raw:
        try:
            started = datetime.fromisoformat(str(started_raw).replace("Z", "+00:00"))
            age = (datetime.now(UTC) - started.astimezone(UTC)).total_seconds()
            if age < stale_seconds:
                return
        except ValueError:
            pass

    _kick_attempted.add(report_id)
    log.info("dil.stale_pending_kick", report_id=report_id)
    schedule_deliberation(report_id, settings, prefer_celery=False)
