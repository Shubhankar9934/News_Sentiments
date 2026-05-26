"""Reverse BWB Assessment Team registry — fixed 3-member panel."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.services.dil_resilience.routing import RoutingConfig
from app.services.deliberation.desk_config import ALL_MODEL_KEYS, default_provider_fallbacks
from app.services.deliberation.schemas import AssessmentRoleKey, ModelKey

ASSESSMENT_LABELS: dict[AssessmentRoleKey, str] = {
    "openai_assessment_analyst": "OpenAI Assessment Analyst",
    "claude_risk_assessment_analyst": "Claude Risk Assessment Analyst",
    "deepseek_quant_assessment_analyst": "DeepSeek Quant Assessment Analyst",
}

_ASSESSMENT_PRIMARIES: dict[AssessmentRoleKey, ModelKey] = {
    "openai_assessment_analyst": "gpt",
    "claude_risk_assessment_analyst": "claude",
    "deepseek_quant_assessment_analyst": "deepseek",
}

ALL_ASSESSMENT_ROLES: tuple[AssessmentRoleKey, ...] = (
    "openai_assessment_analyst",
    "claude_risk_assessment_analyst",
    "deepseek_quant_assessment_analyst",
)


def _default_fallbacks(primary: ModelKey) -> tuple[ModelKey, ...]:
    return default_provider_fallbacks(primary)


@dataclass(frozen=True)
class AssessmentMemberDefinition:
    key: AssessmentRoleKey
    label: str
    primary: ModelKey
    fallbacks: tuple[ModelKey, ...]

    @property
    def provider_chain(self) -> tuple[ModelKey, ...]:
        return (self.primary, *self.fallbacks)


def build_assessment_registry(
    settings: Settings,
) -> dict[AssessmentRoleKey, AssessmentMemberDefinition]:
    routing = RoutingConfig(settings)
    registry: dict[AssessmentRoleKey, AssessmentMemberDefinition] = {}
    for key in ALL_ASSESSMENT_ROLES:
        default_primary = _ASSESSMENT_PRIMARIES[key]
        default_fallbacks = _default_fallbacks(default_primary)
        primary, fallbacks = routing.resolve_assessment_chain(
            key, default_primary, default_fallbacks
        )
        registry[key] = AssessmentMemberDefinition(
            key=key,
            label=ASSESSMENT_LABELS[key],
            primary=primary,  # type: ignore[arg-type]
            fallbacks=fallbacks,  # type: ignore[arg-type]
        )
    return registry


def get_assessment_members(
    settings: Settings,
) -> list[AssessmentMemberDefinition]:
    return list(build_assessment_registry(settings).values())
