"""Tier classification for the canonical NVDA noise examples."""

from app.services.relevance.ticker_relevance import classify_article


def test_direct_when_ticker_in_headline():
    out = classify_article("NVDA slumps amid parabolic data center demand", "", "NVDA")
    assert out.tier == "direct"
    assert out.score == 1.0


def test_direct_when_alias_in_headline():
    out = classify_article("Nvidia and Microsoft back Kawasaki physical AI", "", "NVDA")
    assert out.tier == "direct"


def test_related_sector_for_chip_peer():
    out = classify_article("Qualcomm surges 12%, Skyworks rallies 9%", "", "NVDA")
    assert out.tier == "related_sector"
    assert "Qualcomm".lower() in out.reasons[0].lower() or "QCOM" in out.reasons[0]


def test_macro_when_only_macro_keyword():
    out = classify_article("Dow Jones hits record high as Fed signals patience", "", "NVDA")
    assert out.tier == "macro"


def test_unrelated_for_cava_workday_bjs():
    for title in (
        "Cava Stock Jumped After a Blowout Quarter. Is It Still a Buy?",
        "Why Workday Stock Is Soaring Today",
        "BJ's Wholesale Club Holdings Q1 2026 Earnings Call Summary",
        "Imperial Petroleum Inc. Q1 2026 Earnings Call Summary",
        "Global Ship Lease, Inc. Q1 2026 Earnings Call Summary",
    ):
        out = classify_article(title, "", "NVDA")
        assert out.tier == "unrelated", f"expected unrelated for {title!r}, got {out.tier}"


def test_direct_takes_priority_over_peers():
    # Headline mentions both NVDA and a peer — direct wins
    out = classify_article("Nvidia partners with AMD on AI", "", "NVDA")
    assert out.tier == "direct"


def test_content_fallback_when_headline_clean():
    out = classify_article(
        "Tech sector update",
        "Nvidia released new architecture details today, boosting sentiment.",
        "NVDA",
    )
    assert out.tier == "direct"
