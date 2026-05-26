"""Stage 1: parallel desk research — analysis-only, no trade decisions."""

from __future__ import annotations

import asyncio
import json

import structlog

from app.core.config import settings as global_settings
from app.services.deliberation.desk_config import DeskDefinition
from app.services.deliberation.llm_clients.base import (
    BaseDeliberationClient,
    load_prompt,
    load_role_prompt,
    parse_strict_json,
)
from app.services.deliberation.role_executor import execute_desk
from app.services.deliberation.roles import context_view_for_role, role_step_titles
from app.services.deliberation.schemas import DeliberationContext, DeskResearchReport, ModelKey

log = structlog.get_logger(__name__)


def _build_role_context(
    context: DeliberationContext,
    role_key: str,
    *,
    regime_hint: dict | None = None,
) -> dict:
    return context_view_for_role(
        context.model_dump(), role_key, regime_hint=regime_hint
    )


async def _run_one_desk(
    desk: DeskDefinition,
    client_map: dict[str, BaseDeliberationClient],
    context: DeliberationContext,
    *,
    use_roles: bool,
    regime_hint: dict | None = None,
) -> tuple[str, DeskResearchReport]:
    role_key = desk.key
    role_label = desk.label

    async def _call(client: BaseDeliberationClient) -> DeskResearchReport:
        system = load_prompt("independent_analysis.txt")
        if use_roles:
            role_prompt = load_role_prompt(role_key)
            if role_prompt:
                system = f"{system}\n\n{role_prompt}"

        if use_roles:
            ctx_view = _build_role_context(context, role_key, regime_hint=regime_hint)
            step_titles = role_step_titles(role_key)
            title_hint = "\n".join(f"  {i + 1}. {t}" for i, t in enumerate(step_titles))
            user = (
                f"Ticker: {context.ticker}\n"
                f"Desk role: {role_label}\n\n"
                f"Use these reasoning_steps titles exactly:\n{title_hint}\n\n"
                f"Structured research context (with role_focus block at top):\n"
                f"{json.dumps(ctx_view, indent=2, default=str)}\n\n"
                f'Return JSON with "model" set to "{client.model_key}". '
                f'Include "role_key": "{role_key}" and "role_label": "{role_label}" in the JSON.'
            )
        else:
            ctx_json = json.dumps(context.model_dump(), indent=2, default=str)
            user = (
                f"Ticker: {context.ticker}\n\n"
                f"Structured research context:\n{ctx_json}\n\n"
                f'Return JSON with "model" set to "{client.model_key}".'
            )

        raw = await client.complete_json(system, user)
        report = parse_strict_json(raw, DeskResearchReport)
        report.model = client.model_key  # type: ignore[assignment]
        report.role_key = report.role_key or role_key
        report.role_label = report.role_label or role_label
        return report

    provider, attempts, result, err = await execute_desk(desk, client_map, _call)
    if result is not None and provider is not None:
        result.provider_attempts = attempts
        return role_key, result

    log.warning(
        "dil.analysis.desk_failed",
        desk=role_key,
        attempts=attempts,
        error=err,
    )
    return role_key, DeskResearchReport(
        role_key=role_key,
        role_label=role_label,
        model=(provider or desk.primary),
        analytical_view="neutral",
        confidence_in_analysis=0.0,
        error=err or "No provider available",
        provider_attempts=attempts,
    )


async def run_desk_analysis(
    desks: list[DeskDefinition],
    client_map: dict[str, BaseDeliberationClient],
    context: DeliberationContext,
    *,
    regime_hint: dict | None = None,
) -> dict[str, DeskResearchReport]:
    use_roles = bool(getattr(global_settings, "dil_use_role_specialization", True))

    regime_desk = next((d for d in desks if d.key == "regime_desk"), None)
    other_desks = [d for d in desks if d.key != "regime_desk"]
    hint = regime_hint
    results: dict[str, DeskResearchReport] = {}

    if regime_desk is not None:
        rk, report = await _run_one_desk(
            regime_desk,
            client_map,
            context,
            use_roles=use_roles,
        )
        results[rk] = report
        if not report.error:
            hint = {
                "analytical_view": report.analytical_view,
                "confidence_in_analysis": report.confidence_in_analysis,
                "regime_context": context.regime_context,
            }

    if other_desks:
        batch = await asyncio.gather(
            *[
                _run_one_desk(
                    d,
                    client_map,
                    context,
                    use_roles=use_roles,
                    regime_hint=hint,
                )
                for d in other_desks
            ]
        )
        results.update(dict(batch))

    return results


def client_for_desk_report(
    report: DeskResearchReport,
    client_map: dict[str, BaseDeliberationClient],
    desk: DeskDefinition | None = None,
) -> BaseDeliberationClient | None:
    if report.model and report.model in client_map:
        return client_map[report.model]
    if desk is not None:
        for provider in desk.provider_chain:
            if provider in client_map:
                return client_map[provider]
    return None
