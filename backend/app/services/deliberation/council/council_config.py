"""Decision Council registry — fixed 5-member panel."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.services.dil_resilience.routing import RoutingConfig
from app.services.deliberation.desk_config import ALL_MODEL_KEYS, default_provider_fallbacks
from app.services.deliberation.schemas import CouncilRoleKey, ModelKey

COUNCIL_LABELS: dict[CouncilRoleKey, str] = {
    "portfolio_manager": "Portfolio Manager",
    "risk_manager": "Risk Manager",
    "market_strategist": "Market Strategist",
    "quant_reviewer": "Quant Reviewer",
    "contrarian_investor": "Contrarian Investor",
}

_COUNCIL_PRIMARIES: dict[CouncilRoleKey, ModelKey] = {
    "portfolio_manager": "gpt",
    "risk_manager": "claude",
    "market_strategist": "gemini",
    "quant_reviewer": "deepseek",
    "contrarian_investor": "groq",
}

ALL_COUNCIL_ROLES: tuple[CouncilRoleKey, ...] = (
    "portfolio_manager",
    "risk_manager",
    "market_strategist",
    "quant_reviewer",
    "contrarian_investor",
)


def _default_fallbacks(primary: ModelKey) -> tuple[ModelKey, ...]:
    return default_provider_fallbacks(primary)


@dataclass(frozen=True)
class CouncilMemberDefinition:
    key: CouncilRoleKey
    label: str
    primary: ModelKey
    fallbacks: tuple[ModelKey, ...]

    @property
    def provider_chain(self) -> tuple[ModelKey, ...]:
        return (self.primary, *self.fallbacks)


def build_council_registry(settings: Settings) -> dict[CouncilRoleKey, CouncilMemberDefinition]:
    routing = RoutingConfig(settings)
    registry: dict[CouncilRoleKey, CouncilMemberDefinition] = {}
    for key in ALL_COUNCIL_ROLES:
        default_primary = _COUNCIL_PRIMARIES[key]
        default_fallbacks = _default_fallbacks(default_primary)
        primary, fallbacks = routing.resolve_council_chain(
            key, default_primary, default_fallbacks
        )
        registry[key] = CouncilMemberDefinition(
            key=key,
            label=COUNCIL_LABELS[key],
            primary=primary,  # type: ignore[arg-type]
            fallbacks=fallbacks,  # type: ignore[arg-type]
        )
    return registry


def get_council_members(settings: Settings) -> list[CouncilMemberDefinition]:
    return list(build_council_registry(settings).values())
