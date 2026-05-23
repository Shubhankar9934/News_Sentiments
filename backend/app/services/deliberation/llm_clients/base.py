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
        if isinstance(exc, ClientResponseError):
            return exc.status in (408, 409, 500, 502, 503, 504)
        return isinstance(exc, aiohttp.ClientError)

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(min=2, max=12),
        retry=retry_if_exception(_should_retry),
    )
    async def _post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        timeout_s = getattr(self._settings, "dil_client_timeout_s", 60) or 60
        timeout = ClientTimeout(total=timeout_s)
        start = time.monotonic()
        # Estimate prompt tokens from the payload before the request goes out
        # so we have a number even if the response omits a usage block.
        approx_prompt_tokens = _approx_token_count(json.dumps(payload, default=str))
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                raw = await resp.read()
                elapsed_ms = int((time.monotonic() - start) * 1000)
                if resp.status >= 400:
                    log.error(
                        "dil.llm_error",
                        model=self.model_key,
                        status=resp.status,
                        elapsed_ms=elapsed_ms,
                        body=raw.decode(errors="replace")[:1500],
                    )
                resp.raise_for_status()
                payload_out = json.loads(raw)
                # Provider-reported usage when available, else our estimate.
                usage = payload_out.get("usage") if isinstance(payload_out, dict) else None
                prompt_tokens: int | None = None
                completion_tokens: int | None = None
                if isinstance(usage, dict):
                    prompt_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
                    completion_tokens = usage.get("completion_tokens") or usage.get(
                        "output_tokens"
                    )
                log.info(
                    "dil.llm_call",
                    model=self.model_key,
                    elapsed_ms=elapsed_ms,
                    prompt_tokens=prompt_tokens if prompt_tokens is not None else approx_prompt_tokens,
                    completion_tokens=completion_tokens,
                    approx=prompt_tokens is None,
                )
                return payload_out
