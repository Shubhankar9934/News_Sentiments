"""Tests for council consensus (deterministic Round 4)."""

from app.services.deliberation.council.round4_consensus import synthesize_council_consensus
from app.services.deliberation.schemas import (
    CouncilMemberDecision,
    CouncilRevision,
)


def test_consensus_majority_wait():
    round1 = {
        "portfolio_manager": CouncilMemberDecision(
            model="gpt",
            council_role="portfolio_manager",
            council_label="Portfolio Manager",
            decision="WAIT",
            confidence=0.7,
        ),
        "risk_manager": CouncilMemberDecision(
            model="claude",
            council_role="risk_manager",
            council_label="Risk Manager",
            decision="AVOID",
            confidence=0.8,
        ),
        "market_strategist": CouncilMemberDecision(
            model="gemini",
            council_role="market_strategist",
            council_label="Market Strategist",
            decision="WAIT",
            confidence=0.6,
        ),
        "quant_reviewer": CouncilMemberDecision(
            model="deepseek",
            council_role="quant_reviewer",
            council_label="Quant Reviewer",
            decision="WAIT",
            confidence=0.65,
        ),
        "contrarian_investor": CouncilMemberDecision(
            model="groq",
            council_role="contrarian_investor",
            council_label="Contrarian Investor",
            decision="ENTER",
            confidence=0.55,
        ),
    }
    round3 = {
        k: CouncilRevision(
            model=v.model,
            council_role=v.council_role,
            council_label=v.council_label,
            prior_decision=v.decision,
            revised_decision=v.decision,
            prior_confidence=v.confidence,
            revised_confidence=v.confidence,
        )
        for k, v in round1.items()
    }
    consensus = synthesize_council_consensus(round1, {}, round3)
    assert consensus.decision == "WAIT"
    assert consensus.support["WAIT"] == 3
    assert consensus.support["ENTER"] == 1
    assert consensus.support["AVOID"] == 1


def test_consensus_tie_breaks_to_wait():
    round1 = {
        "portfolio_manager": CouncilMemberDecision(
            model="gpt",
            council_role="portfolio_manager",
            council_label="PM",
            decision="ENTER",
            confidence=0.7,
        ),
        "risk_manager": CouncilMemberDecision(
            model="claude",
            council_role="risk_manager",
            council_label="RM",
            decision="AVOID",
            confidence=0.7,
        ),
    }
    round3 = {
        k: CouncilRevision(
            model=v.model,
            council_role=v.council_role,
            council_label=v.council_label,
            prior_decision=v.decision,
            revised_decision=v.decision,
            prior_confidence=v.confidence,
            revised_confidence=v.confidence,
        )
        for k, v in round1.items()
    }
    consensus = synthesize_council_consensus(round1, {}, round3)
    assert consensus.decision == "WAIT"
