"""Role specialization for the DIL panel — re-exports from desk_config."""

from __future__ import annotations

from app.services.deliberation.desk_config import (
    ALL_DESK_KEYS,
    CORE_DESK_KEYS,
    DEFAULT_ROLE,
    DESK_LABELS,
    DESK_ROLES,
    ROLE_STEP_TITLES,
    DeskDefinition,
    build_desk_registry,
    context_view_for_role,
    desk_label,
    get_active_desks,
    role_for,
    role_step_titles,
)

__all__ = [
    "ALL_DESK_KEYS",
    "CORE_DESK_KEYS",
    "DEFAULT_ROLE",
    "DESK_LABELS",
    "DESK_ROLES",
    "ROLE_STEP_TITLES",
    "DeskDefinition",
    "build_desk_registry",
    "context_view_for_role",
    "desk_label",
    "get_active_desks",
    "role_for",
    "role_step_titles",
]
