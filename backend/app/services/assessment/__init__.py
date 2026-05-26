"""Reverse BWB Assessment Team.

A 3-member panel (OpenAI / Claude / DeepSeek) that owns every field of
the Reverse BWB Credit View card except the trade ``decision``. The team
runs a 4-round debate (independent → critique → revision → consensus)
over a unified intelligence package built from the 13 research desks.
"""

from app.services.assessment.team_service import run_assessment_team

__all__ = ["run_assessment_team"]
