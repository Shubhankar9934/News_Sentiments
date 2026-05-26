"""Shared quorum evaluation for assessment and council panels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QuorumResult:
    valid_count: int
    required: int
    total: int
    meets_quorum: bool
    degraded: bool
    failed_roles: tuple[str, ...]

    def to_meta(self) -> dict[str, Any]:
        return {
            "valid": self.valid_count,
            "total": self.total,
            "required": self.required,
            "degraded": self.degraded,
            "meets_quorum": self.meets_quorum,
            "failed_roles": list(self.failed_roles),
        }


class QuorumEvaluator:
    @staticmethod
    def evaluate(
        round1: dict[str, Any],
        *,
        required: int,
        total: int | None = None,
        error_attr: str = "error",
    ) -> QuorumResult:
        total_count = total if total is not None else len(round1)
        valid_roles = [k for k, v in round1.items() if not getattr(v, error_attr, None)]
        failed_roles = [k for k in round1 if k not in valid_roles]
        valid_count = len(valid_roles)
        meets = valid_count >= required
        degraded = meets and valid_count < total_count
        return QuorumResult(
            valid_count=valid_count,
            required=required,
            total=total_count,
            meets_quorum=meets,
            degraded=degraded,
            failed_roles=tuple(failed_roles),
        )
