"""Shared provider failover executor for desk, assessment, and council."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

import structlog

from app.services.dil_resilience.context import dil_role_context, set_dil_role_context
from app.services.dil_resilience.registry import get_resilience_gateway
from app.services.deliberation.llm_clients.base import BaseDeliberationClient
from app.services.deliberation.schemas import ModelKey

log = structlog.get_logger(__name__)

T = TypeVar("T")


async def execute_with_failover(
    role_key: str,
    provider_chain: tuple[str, ...],
    client_map: dict[str, BaseDeliberationClient],
    prompt_fn: Callable[[BaseDeliberationClient], Awaitable[T]],
    *,
    log_prefix: str = "desk",
) -> tuple[ModelKey | None, list[str], T | None, str | None]:
    """Try each provider in chain until one succeeds.

    Returns ``(provider_used, attempts, result, error)``.
    """
    gateway = get_resilience_gateway()
    filtered = gateway.filter_provider_chain(provider_chain)
    attempts: list[str] = []
    last_error: str | None = None
    start = time.monotonic()

    ctx_token = set_dil_role_context(f"{log_prefix}:{role_key}")
    try:
        for provider in filtered:
            client = client_map.get(provider)
            if client is None:
                continue
            attempts.append(provider)
            try:
                result = await prompt_fn(client)
                if len(attempts) > 1:
                    gateway.metrics.record_failover(provider)
                    log.info(
                        f"dil.{log_prefix}.failover",
                        **{log_prefix: role_key} if log_prefix == "desk" else {"role": role_key},
                        provider=provider,
                        attempts=attempts,
                    )
                latency_ms = (time.monotonic() - start) * 1000
                if log_prefix == "desk":
                    gateway.metrics.record_desk(
                        role_key,
                        success=True,
                        failover_count=max(0, len(attempts) - 1),
                        latency_ms=latency_ms,
                    )
                return provider, attempts, result, None  # type: ignore[return-value]
            except Exception as e:
                last_error = str(e)
                log.warning(
                    f"dil.{log_prefix}.provider_failed",
                    **{log_prefix: role_key} if log_prefix == "desk" else {"role": role_key},
                    provider=provider,
                    error=last_error,
                )
                continue
    finally:
        dil_role_context.reset(ctx_token)

    latency_ms = (time.monotonic() - start) * 1000
    if log_prefix == "desk":
        gateway.metrics.record_desk(
            role_key,
            success=False,
            failover_count=max(0, len(attempts) - 1),
            latency_ms=latency_ms,
        )

    return None, attempts, None, last_error or f"No provider available for {role_key}"
