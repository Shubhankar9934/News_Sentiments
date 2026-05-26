"""Tests for 429-aware retry handling."""

from __future__ import annotations

import pytest

from app.services.dil_resilience.retry import RetryAfterHandler


def test_parse_retry_after_header() -> None:
    handler = RetryAfterHandler()
    delay = handler.parse_retry_after(
        "gpt",
        429,
        {"Retry-After": "14"},
        "",
    )
    assert delay == 14.0


def test_parse_openai_body_message() -> None:
    handler = RetryAfterHandler()
    body = (
        '{"error":{"message":"Rate limit reached. Please try again in 14.308s."}}'
    )
    delay = handler.parse_retry_after("gpt", 429, {}, body)
    assert delay == pytest.approx(14.308)


def test_parse_groq_body_minutes_and_seconds() -> None:
    handler = RetryAfterHandler(max_wait_s=500.0)
    body = (
        '{"error":{"message":"Please try again in 7m6.816s."}}'
    )
    delay = handler.parse_retry_after("groq", 429, {}, body)
    assert delay == pytest.approx(7 * 60 + 6.816)


def test_caps_delay_at_max_wait() -> None:
    handler = RetryAfterHandler(max_wait_s=10.0)
    delay = handler.parse_retry_after(
        "gpt",
        429,
        {"Retry-After": "120"},
        "",
    )
    assert delay == 10.0


def test_daily_quota_is_non_retryable() -> None:
    body = (
        '{"error":{"message":"Rate limit reached for model `llama-3.3-70b-versatile` '
        'on tokens per day (TPD): Limit 100000, Used 96447, Requested 12230. '
        'Please try again in 2h4m56.928s."}}'
    )
    assert RetryAfterHandler.is_non_retryable_quota(body) is True
