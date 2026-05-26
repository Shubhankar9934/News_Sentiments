"""Reverse BWB Intelligence Dashboard service package.

Coordinates the per-ticker workflow that powers the watchlist grid:

    1. Run the existing research pipeline -> full report dict
    2. LLM-synthesize a Reverse BWB trader summary from that report
    3. Generate placeholder option opportunities (CALL + PUT combos)
    4. Persist all three artifacts to dashboard tables

See ``watchlist_batch.py`` for the sequential orchestrator used by both the
FastAPI startup hook and the manual refresh endpoints.
"""
