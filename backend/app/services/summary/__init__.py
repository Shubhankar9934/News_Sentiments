"""Executive-summary extractor for the multi-ticker grid dashboard.

Layer-1 grid cards render exclusively from `ExecutiveSummary` blocks. The block
is derived deterministically from already-existing report fields — no new LLM
call. See ``extractor.extract_executive_summary``.
"""

from app.services.summary.extractor import extract_executive_summary
from app.services.summary.schemas import ExecutiveSummary

__all__ = ["ExecutiveSummary", "extract_executive_summary"]
