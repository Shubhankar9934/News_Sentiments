"""Explainability layer — the "Why?" reasoning behind every dashboard card value.

This package owns the assembly of ``report_json.explainability``, the
versioned container served by ``GET /api/v1/dashboard/tickers/{ticker}/report``.

The card schema (``ReverseBwbSummary``) is completely unaffected; every
sub-block here is additive and only travels inside the full-report
endpoint payload.
"""

from app.services.explainability.assembler import (
    ExplainabilityAssembler,
    assemble_explainability,
)

__all__ = ["ExplainabilityAssembler", "assemble_explainability"]
