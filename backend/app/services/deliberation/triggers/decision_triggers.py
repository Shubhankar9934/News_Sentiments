"""Decision trigger evaluation — when to activate the Decision Council."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.services.deliberation.schemas import IntelligencePackage


@dataclass(frozen=True)
class DecisionTriggerResult:
    should_run_council: bool
    trigger: str
    question: str


def _trigger_reverse_bwb(report: dict[str, Any]) -> DecisionTriggerResult | None:
    oi = report.get("options_intelligence") or {}
    if not oi or not oi.get("reverse_bwb"):
        return None
    return DecisionTriggerResult(
        should_run_council=True,
        trigger="reverse_bwb",
        question="Should we enter this Reverse BWB?",
    )


def _trigger_ticker_avoidance(report: dict[str, Any]) -> DecisionTriggerResult | None:
    oi = report.get("options_intelligence") or {}
    credit = oi.get("credit_safety") or {}
    event = oi.get("event_risk") or {}
    score = credit.get("score")
    if score is not None and float(score) < 4:
        return DecisionTriggerResult(
            should_run_council=True,
            trigger="ticker_avoidance",
            question="Should we avoid this ticker?",
        )
    level = str(event.get("level") or event.get("label") or "").lower()
    if level in ("high", "extreme", "elevated"):
        return DecisionTriggerResult(
            should_run_council=True,
            trigger="ticker_avoidance",
            question="Should we avoid this ticker?",
        )
    return None


def _trigger_size_reduction(report: dict[str, Any]) -> DecisionTriggerResult | None:
    oi = report.get("options_intelligence") or {}
    body = oi.get("body_danger") or {}
    pin = oi.get("pin_risk") or {}
    body_level = str(body.get("level") or body.get("label") or "").lower()
    pin_level = str(pin.get("level") or pin.get("label") or "").lower()
    if body_level in ("high", "extreme", "elevated") or pin_level in (
        "high",
        "extreme",
        "elevated",
    ):
        return DecisionTriggerResult(
            should_run_council=True,
            trigger="size_reduction",
            question="Should we reduce size?",
        )
    return None


_TRIGGER_HANDLERS = {
    "reverse_bwb": _trigger_reverse_bwb,
    "ticker_avoidance": _trigger_ticker_avoidance,
    "size_reduction": _trigger_size_reduction,
}


def evaluate_decision_trigger(
    report: dict[str, Any],
    intel: IntelligencePackage,
    settings: Settings,
) -> DecisionTriggerResult:
    active = settings.dil_council_trigger_set
    for key in ("reverse_bwb", "ticker_avoidance", "size_reduction"):
        if key not in active:
            continue
        handler = _TRIGGER_HANDLERS.get(key)
        if handler is None:
            continue
        result = handler(report)
        if result is not None:
            return result

    return DecisionTriggerResult(
        should_run_council=False,
        trigger="none",
        question="",
    )
