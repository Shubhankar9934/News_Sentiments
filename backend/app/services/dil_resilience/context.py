"""Context variables for DIL resilience (role attribution in metrics/logs)."""

from __future__ import annotations

import contextvars

dil_role_context: contextvars.ContextVar[str] = contextvars.ContextVar(
    "dil_role_context",
    default="",
)


def set_dil_role_context(role: str) -> contextvars.Token[str]:
    """Set the active DIL role (e.g. ``desk:macro_desk``) for the current task."""
    return dil_role_context.set(role)
