"""Desk analysis layer — research-only outputs."""

from app.services.deliberation.analysis.adapters import (
    desk_report_to_opinion,
    opinion_to_desk_report,
)
from app.services.deliberation.analysis.run_desk_analysis import run_desk_analysis

__all__ = [
    "desk_report_to_opinion",
    "opinion_to_desk_report",
    "run_desk_analysis",
]
