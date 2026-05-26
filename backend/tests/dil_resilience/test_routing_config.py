"""Tests for config-driven provider routing."""

from __future__ import annotations

from app.core.config import Settings
from app.services.deliberation.desk_config import build_desk_registry
from app.services.dil_resilience.routing import RoutingConfig


def test_full_routing_override() -> None:
    settings = Settings(
        DIL_EXCLUDE_MODELS="",
        DIL_DESK_ROUTING="macro_desk=claude,gemini,gpt",
    )
    routing = RoutingConfig(settings)
    primary, fallbacks = routing.resolve_desk_chain(
        "macro_desk", "gpt", ("claude", "gemini")
    )
    assert primary == "claude"
    assert fallbacks == ("gemini", "gpt")


def test_fallback_only_override_preserves_default_primary() -> None:
    settings = Settings(
        DIL_DESK_FALLBACKS="macro_desk=claude,gemini,deepseek,groq",
    )
    registry = build_desk_registry(settings)
    desk = registry["macro_desk"]
    assert desk.primary == "gpt"
    assert desk.fallbacks[0] == "claude"


def test_routing_precedence_over_fallbacks() -> None:
    settings = Settings(
        DIL_DESK_ROUTING="options_desk=gpt,deepseek,claude",
        DIL_DESK_FALLBACKS="options_desk=claude,gemini",
    )
    registry = build_desk_registry(settings)
    desk = registry["options_desk"]
    assert desk.primary == "gpt"
    assert desk.fallbacks == ("deepseek", "claude")


def test_invalid_provider_skipped() -> None:
    settings = Settings(
        DIL_EXCLUDE_MODELS="",
        DIL_DESK_ROUTING="risk_desk=claude,not_a_model,gpt",
    )
    routing = RoutingConfig(settings)
    primary, fallbacks = routing.resolve_desk_chain("risk_desk", "deepseek", ("gpt",))
    assert primary == "claude"
    assert fallbacks == ("gpt",)


def test_openai_alias_maps_to_gpt() -> None:
    settings = Settings(
        DIL_EXCLUDE_MODELS="",
        DIL_COUNCIL_ROUTING="portfolio_manager=openai,claude,deepseek",
    )
    routing = RoutingConfig(settings)
    primary, fallbacks = routing.resolve_council_chain(
        "portfolio_manager", "gpt", ("claude", "deepseek")
    )
    assert primary == "gpt"
    assert fallbacks == ("claude", "deepseek")
