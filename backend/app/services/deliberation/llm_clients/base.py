"""Shared LLM client utilities for deliberation."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, TypeVar

import aiohttp
import json_repair
import structlog
from aiohttp import ClientResponseError, ClientTimeout
from pydantic import BaseModel
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.config import Settings
from app.services.deliberation.schemas import ModelKey
from app.services.dil_resilience.registry import get_resilience_gateway
from app.services.dil_resilience.retry import RateLimitError

log = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _approx_token_count(text: str) -> int:
    """Cheap, dependency-free token estimate (~4 chars/token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def load_role_prompt(role_key: str) -> str:
    """Load a per-desk role prompt. Returns empty string when missing
    so the caller can degrade gracefully to the generic prompt."""
    path = PROMPTS_DIR / "roles" / f"{role_key}.txt"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def load_council_prompt(role_key: str) -> str:
    """Load a per-council-member role prompt."""
    path = PROMPTS_DIR / "council" / f"{role_key}.txt"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def parse_strict_json(blob: str, model: type[T]) -> T:
    clean = blob.replace("```json", "").replace("```", "").strip()
    start, end = clean.find("{"), clean.rfind("}")
    if start == -1:
        raise ValueError("No JSON object in model response")
    fragment = clean[start : end + 1]
    try:
        data = json.loads(fragment)
    except json.JSONDecodeError:
        data = json_repair.loads(fragment)
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return model.model_validate(data)


class BaseDeliberationClient(ABC):
    model_key: ModelKey

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @abstractmethod
    async def complete_json(self, system: str, user: str, max_tokens: int = 3000) -> str:
        """Return raw text expected to contain a JSON object."""

    @staticmethod
    def _should_retry(exc: BaseException) -> bool:
        if isinstance(exc, RateLimitError):
            return False
        if isinstance(exc, ClientResponseError):
            return exc.status in (408, 409, 500, 502, 503, 504)
        return isinstance(exc, aiohttp.ClientError)

    async def _post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        gateway = get_resilience_gateway()
        if gateway.enabled:
            return await self._post_json_resilient(url, headers, payload)
        return await self._post_json_with_tenacity(url, headers, payload)

    async def _post_json_resilient(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        gateway = get_resilience_gateway()
        await gateway.before_request(self.model_key)
        start = time.monotonic()
        released = False
        try:
            result = await self._post_json_with_tenacity(url, headers, payload)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            await gateway.after_request(
                self.model_key, success=True, latency_ms=elapsed_ms
            )
            released = True
            return result
        except RateLimitError:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            await gateway.after_request(
                self.model_key,
                success=False,
                latency_ms=elapsed_ms,
                is_rate_limit=True,
            )
            released = True
            raise
        except Exception:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            await gateway.after_request(
                self.model_key, success=False, latency_ms=elapsed_ms
            )
            released = True
            raise
        finally:
            if not released:
                await gateway.concurrency.release()

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(min=2, max=12),
        retry=retry_if_exception(_should_retry),
    )
    async def _post_json_with_tenacity(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._post_json_once(url, headers, payload)

    async def _post_json_once(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        gateway = get_resilience_gateway()
        timeout_s = getattr(self._settings, "dil_client_timeout_s", 60) or 60
        timeout = ClientTimeout(total=timeout_s)
        approx_prompt_tokens = _approx_token_count(json.dumps(payload, default=str))

        rate_limit_attempt = 0
        while True:
            start = time.monotonic()
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    raw = await resp.read()
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    body_text = raw.decode(errors="replace")
                    resp_headers = {k: v for k, v in resp.headers.items()}

                    if resp.status == 429 and gateway.enabled:
                        log.error(
                            "dil.llm_error",
                            model=self.model_key,
                            status=resp.status,
                            elapsed_ms=elapsed_ms,
                            body=body_text[:1500],
                        )
                        should_retry = await gateway.handle_429(
                            self.model_key,
                            resp.status,
                            resp_headers,
                            body_text,
                            rate_limit_attempt,
                        )
                        if should_retry:
                            rate_limit_attempt += 1
                            continue
                        gateway.raise_rate_limit(
                            self.model_key, resp.status, body_text
                        )

                    if resp.status >= 400:
                        log.error(
                            "dil.llm_error",
                            model=self.model_key,
                            status=resp.status,
                            elapsed_ms=elapsed_ms,
                            body=body_text[:1500],
                        )
                    resp.raise_for_status()
                    payload_out = json.loads(raw)
                    usage = (
                        payload_out.get("usage")
                        if isinstance(payload_out, dict)
                        else None
                    )
                    prompt_tokens: int | None = None
                    completion_tokens: int | None = None
                    if isinstance(usage, dict):
                        prompt_tokens = usage.get("prompt_tokens") or usage.get(
                            "input_tokens"
                        )
                        completion_tokens = usage.get(
                            "completion_tokens"
                        ) or usage.get("output_tokens")
                    log.info(
                        "dil.llm_call",
                        model=self.model_key,
                        elapsed_ms=elapsed_ms,
                        prompt_tokens=(
                            prompt_tokens
                            if prompt_tokens is not None
                            else approx_prompt_tokens
                        ),
                        completion_tokens=completion_tokens,
                        approx=prompt_tokens is None,
                        rate_limit_retries=rate_limit_attempt,
                    )
                    return payload_out
