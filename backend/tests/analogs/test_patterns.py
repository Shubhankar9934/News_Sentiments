"""Pattern detectors flag the kind of historical analog the user actually wants."""

from app.services.analogs.patterns import (
    detect_earnings_beat_sell_off,
    detect_sector_rotation,
)


def test_earnings_beat_sell_off_flagged():
    rows = [
        {"headline": "NVDA earnings beat — stock slumps post-earnings on guidance"},
        {"headline": "AAPL guidance beat — sell-the-news reaction drops shares 3%"},
        {"headline": "TSLA beats estimates — rallies on strong delivery numbers"},
        {"headline": "Random macro headline"},
    ]
    out = detect_earnings_beat_sell_off(rows)
    headlines = [r["headline"] for r in out]
    assert any("NVDA" in h for h in headlines)
    assert any("sell-the-news" in h.lower() for h in headlines)
    assert not any("rallies" in h.lower() for h in headlines)
    for r in out:
        assert r["match_reason"] == "earnings_beat_sell_off"
        assert r["match_score"] >= 0.8


def test_sector_rotation_flagged():
    rows = [
        {"headline": "Sector rotation away from mega-cap tech intensifies"},
        {"headline": "Smaller-cap chips outperform while NVDA underperforms"},
        {"headline": "Unrelated business news"},
    ]
    out = detect_sector_rotation(rows)
    assert len(out) == 2
    for r in out:
        assert r["match_reason"] == "sector_rotation"
