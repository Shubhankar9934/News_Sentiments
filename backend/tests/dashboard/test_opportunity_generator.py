"""Deterministic shape tests for the placeholder opportunity generator."""

from __future__ import annotations

from app.services.dashboard.opportunity_generator import PlaceholderOpportunitySource


def test_generates_two_calls_and_two_puts(sample_report):
    source = PlaceholderOpportunitySource()
    opps = source.generate("NVDA", sample_report)
    assert len(opps.calls) == 2
    assert len(opps.puts) == 2


def test_call_strikes_above_price_and_put_strikes_below(sample_report):
    source = PlaceholderOpportunitySource()
    opps = source.generate("NVDA", sample_report)
    last_close = sample_report["options_intelligence"]["last_close"]

    for opp in opps.calls:
        first_strike = float(opp.combo.split("/")[0])
        assert first_strike >= last_close, (
            f"CALL inner short {first_strike} should be at or above last close {last_close}"
        )

    for opp in opps.puts:
        first_strike = float(opp.combo.split("/")[0])
        assert first_strike <= last_close, (
            f"PUT inner short {first_strike} should be at or below last close {last_close}"
        )


def test_combo_has_three_strikes(sample_report):
    opps = PlaceholderOpportunitySource().generate("NVDA", sample_report)
    for opp in opps.calls + opps.puts:
        parts = opp.combo.split("/")
        assert len(parts) == 3, f"expected 3-leg combo, got {opp.combo}"


def test_etf_gets_good_liquidity(sample_report):
    spy_report = dict(sample_report)
    opps = PlaceholderOpportunitySource().generate("SPY", spy_report)
    # ETFs are mapped to the narrowed ``Good`` liquidity bucket under
    # the Poor/Average/Good vocabulary.
    assert all(o.liquidity == "Good" for o in opps.calls + opps.puts)


def test_skips_when_options_intelligence_missing(sample_report):
    barebones = {k: v for k, v in sample_report.items() if k != "options_intelligence"}
    opps = PlaceholderOpportunitySource().generate("NVDA", barebones)
    assert opps.calls == []
    assert opps.puts == []


def test_margins_and_premiums_positive(sample_report):
    opps = PlaceholderOpportunitySource().generate("NVDA", sample_report)
    for opp in opps.calls + opps.puts:
        assert opp.premium > 0.0
        assert opp.margin > 0.0
