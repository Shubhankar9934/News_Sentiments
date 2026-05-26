"""End-to-end smoke test for the OptionsIntelligenceService composition."""

from dataclasses import dataclass

from app.core.config import Settings
from app.services.options import OptionsIntelligenceService


@dataclass
class _Bar:
    close: float


def _make_bars(prices: list[float]) -> list[_Bar]:
    return [_Bar(close=p) for p in prices]


def test_service_returns_block_for_realistic_inputs():
    svc = OptionsIntelligenceService(Settings())
    # synthetic NVDA-ish path
    prices = [220.0, 218.5, 222.0, 219.0, 224.0, 221.0, 219.5]
    out = svc.compute(
        last_close=219.5,
        bars=_make_bars(prices),
        volatility_regime="medium",
        key_events=[{"type": "Earnings", "description": "Q1 beat", "impact": "High"}],
    )
    assert out is not None
    assert out.last_close == 219.5
    assert out.expected_range.low < out.expected_range.high
    assert 0.0 < out.expected_range.confidence <= 1.0
    assert 0.0 <= out.move_probabilities.p_up_2pct <= 1.0
    assert 0.0 <= out.credit_safety.score <= 10.0
    assert out.reverse_bwb.suggested_dte >= 1


def test_service_skips_when_last_close_missing():
    svc = OptionsIntelligenceService(Settings())
    out = svc.compute(
        last_close=None,
        bars=_make_bars([100.0, 101.0]),
        volatility_regime="low",
        key_events=[],
    )
    assert out is None


def test_live_iv_path_uses_iv_when_provided():
    svc = OptionsIntelligenceService(Settings())
    bars = _make_bars([100.0] * 20)  # zero realized vol
    out_realized = svc.compute(
        last_close=100.0, bars=bars, volatility_regime="low", key_events=[]
    )
    out_live = svc.compute(
        last_close=100.0,
        bars=bars,
        volatility_regime="low",
        key_events=[],
        live_iv_pct=40.0,  # 40% annualized IV
    )
    assert out_realized is not None and out_live is not None
    assert out_live.source == "live_iv"
    assert out_live.daily_vol_pct > out_realized.daily_vol_pct
