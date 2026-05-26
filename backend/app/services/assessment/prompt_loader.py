"""Filesystem prompt loader for the Assessment Team."""

from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_assessment_prompt(name: str) -> str:
    """Load a prompt from ``backend/app/services/assessment/prompts/``."""

    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def load_assessment_role_prompt(role_key: str) -> str:
    """Load a per-member role prompt; returns empty if missing."""

    path = PROMPTS_DIR / "roles" / f"{role_key}.txt"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")
