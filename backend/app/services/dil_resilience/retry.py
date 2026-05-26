"""429-aware retry handling with Retry-After parsing."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Mapping

import structlog

log = structlog.get_logger(__name__)

# OpenAI / Groq / DeepSeek: "Please try again in 14.308s" or "7m6.816s"
_RETRY_IN_SECONDS = re.compile(
    r"try again in\s+(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?",
    re.IGNORECASE,
)
_RETRY_IN_SECONDS_SIMPLE = re.compile(r"try again in\s+(\d+(?:\.\d+)?)s", re.IGNORECASE)


class RateLimitError(Exception):
    """Raised when a provider returns 429 after retries are exhausted."""

    def __init__(self, provider: str, status: int, message: str = "") -> None:
        self.provider = provider
        self.status = status
        super().__init__(message or f"Rate limit exceeded for {provider}")


class RetryAfterHandler:
    """Parse Retry-After headers/bodies and sleep before same-provider retry."""

    def __init__(
        self,
        *,
        max_retries: int = 1,
        max_wait_s: float = 60.0,
        base_backoff_s: float = 2.0,
    ) -> None:
        self.max_retries = max(0, max_retries)
        self.max_wait_s = max(0.0, max_wait_s)
        self.base_backoff_s = base_backoff_s

    def parse_retry_after(
        self,
        provider: str,
        status: int,
        headers: Mapping[str, str] | None,
        body: str,
    ) -> float:
        if status != 429:
            return self.base_backoff_s

        hdrs = {k.lower(): v for k, v in (headers or {}).items()}
        retry_hdr = hdrs.get("retry-after")
        if retry_hdr:
            try:
                return min(float(retry_hdr), self.max_wait_s)
            except ValueError:
                pass

        delay = self._parse_body(provider, body)
        if delay is not None:
            return min(delay, self.max_wait_s)

        return min(self.base_backoff_s, self.max_wait_s)

    @staticmethod
    def is_non_retryable_quota(body: str) -> bool:
        """Daily/hourly quota exhaustion — fail over immediately, do not sleep-retry."""
        text = body.lower()
        if "tokens per day" in text or "(tpd)" in text:
            return True
        delay = RetryAfterHandler._parse_body_static(body)
        return delay is not None and delay > 120.0

    @staticmethod
    def _parse_body_static(body: str) -> float | None:
        if not body:
            return None
        m = _RETRY_IN_SECONDS.search(body)
        if m:
            minutes = float(m.group(1) or 0)
            seconds = float(m.group(2) or 0)
            total = minutes * 60 + seconds
            if total > 0:
                return total
        m2 = _RETRY_IN_SECONDS_SIMPLE.search(body)
        if m2:
            return float(m2.group(1))
        return None

    def _parse_body(self, provider: str, body: str) -> float | None:
        if not body:
            return None

        # Gemini RetryInfo in JSON error payload
        if provider == "gemini":
            try:
                data = json.loads(body)
                err = data.get("error") if isinstance(data, dict) else None
                if isinstance(err, dict):
                    details = err.get("details") or []
                    for detail in details:
                        if not isinstance(detail, dict):
                            continue
                        if detail.get("@type", "").endswith("RetryInfo"):
                            delay_str = (detail.get("retryDelay") or "").rstrip("s")
                            if delay_str:
                                return float(delay_str)
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        return self._parse_body_static(body)

    async def sleep_before_retry(
        self,
        provider: str,
        attempt: int,
        delay_s: float,
    ) -> None:
        capped = min(max(0.0, delay_s), self.max_wait_s)
        log.info(
            "dil.resilience.retry.wait",
            provider=provider,
            attempt=attempt,
            delay_s=capped,
        )
        await asyncio.sleep(capped)
