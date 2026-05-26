"""Config-driven provider routing for desks, assessment, and council."""

from __future__ import annotations

import structlog

from app.core.config import Settings

log = structlog.get_logger(__name__)

VALID_PROVIDERS = frozenset({"gpt", "claude", "gemini", "deepseek", "groq"})
PROVIDER_ALIASES: dict[str, str] = {
    "openai": "gpt",
    "chatgpt": "gpt",
    "anthropic": "claude",
}


def _canonical_provider(provider: str) -> str:
    key = provider.strip().lower()
    return PROVIDER_ALIASES.get(key, key)


def _parse_routing_raw(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    text = raw.strip()
    if not text:
        return out
    for segment in text.split(";"):
        segment = segment.strip()
        if not segment or "=" not in segment:
            continue
        role, providers = segment.split("=", 1)
        out[role.strip().lower()] = providers.strip()
    return out


def _normalize_chain(
    providers_raw: str,
    *,
    excluded: set[str],
    role_key: str,
) -> tuple[str, ...] | None:
    parts = [_canonical_provider(p) for p in providers_raw.split(",") if p.strip()]
    if not parts:
        return None

    seen: set[str] = set()
    chain: list[str] = []
    for p in parts:
        if p not in VALID_PROVIDERS:
            log.warning(
                "dil.resilience.routing.invalid_provider",
                role=role_key,
                provider=p,
            )
            continue
        if p in excluded:
            log.warning(
                "dil.resilience.routing.excluded_provider",
                role=role_key,
                provider=p,
            )
            continue
        if p in seen:
            continue
        seen.add(p)
        chain.append(p)  # type: ignore[arg-type]

    if not chain:
        log.warning("dil.resilience.routing.empty_chain", role=role_key)
        return None
    return tuple(chain)  # type: ignore[return-value]


class RoutingConfig:
    """Parse and resolve full provider chains from env configuration."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._desk_routing = _parse_routing_raw(
            getattr(settings, "dil_desk_routing_raw", "") or ""
        )
        self._assessment_routing = _parse_routing_raw(
            getattr(settings, "dil_assessment_routing_raw", "") or ""
        )
        self._council_routing = _parse_routing_raw(
            getattr(settings, "dil_council_routing_raw", "") or ""
        )
        custom = (
            len(self._desk_routing)
            + len(self._assessment_routing)
            + len(self._council_routing)
        )
        self.custom_chain_count = custom

    @property
    def excluded(self) -> set[str]:
        return self._settings.dil_excluded_model_set

    def resolve_desk_chain(
        self,
        desk_key: str,
        default_primary: str,
        default_fallbacks: tuple[str, ...],
    ) -> tuple[str, tuple[str, ...]]:
        full = self._resolve(
            desk_key,
            routing_map=self._desk_routing,
            fallback_map=self._settings.dil_desk_fallbacks,
            default_primary=default_primary,
            default_fallbacks=default_fallbacks,
        )
        primary, fallbacks = full[0], full[1:]
        return primary, fallbacks

    def resolve_assessment_chain(
        self,
        role_key: str,
        default_primary: str,
        default_fallbacks: tuple[str, ...],
    ) -> tuple[str, tuple[str, ...]]:
        full = self._resolve(
            role_key,
            routing_map=self._assessment_routing,
            fallback_map=self._settings.dil_assessment_fallbacks,
            default_primary=default_primary,
            default_fallbacks=default_fallbacks,
        )
        return full[0], full[1:]

    def resolve_council_chain(
        self,
        role_key: str,
        default_primary: str,
        default_fallbacks: tuple[str, ...],
    ) -> tuple[str, tuple[str, ...]]:
        full = self._resolve(
            role_key,
            routing_map=self._council_routing,
            fallback_map=self._settings.dil_council_fallbacks,
            default_primary=default_primary,
            default_fallbacks=default_fallbacks,
        )
        return full[0], full[1:]

    def _resolve(
        self,
        role_key: str,
        *,
        routing_map: dict[str, str],
        fallback_map: dict[str, str],
        default_primary: str,
        default_fallbacks: tuple[str, ...],
    ) -> tuple[str, ...]:
        key = role_key.lower()

        # 1. Full routing override
        if key in routing_map:
            chain = _normalize_chain(
                routing_map[key], excluded=self.excluded, role_key=key
            )
            if chain:
                return chain

        # 2. Fallback-only override
        if key in fallback_map:
            fb = _normalize_chain(
                fallback_map[key], excluded=self.excluded, role_key=key
            )
            if fb:
                primary = default_primary
                if primary in self.excluded and fb:
                    primary = fb[0]
                    fb = fb[1:]
                fallbacks = tuple(p for p in fb if p != primary)
                return (primary, *fallbacks)

        # 3. Code defaults
        primary = default_primary
        fallbacks = tuple(
            p for p in default_fallbacks if p != primary and p not in self.excluded
        )
        if primary in self.excluded:
            if fallbacks:
                return (fallbacks[0], *fallbacks[1:])
            return (primary,)
        return (primary, *fallbacks)
