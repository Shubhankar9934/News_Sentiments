"""Static ticker → company-name aliases and sector-peer lists.

Kept as a small in-process dict for the top tickers — no DB lookups in the
hot path. Easy to extend; falls back to ``[ticker]`` aliases when an entry
is missing.
"""

from __future__ import annotations

# Canonical aliases used to detect "direct" mentions when the bare ticker
# isn't in the headline. All values are lowercased at lookup time.
TICKER_ALIASES: dict[str, list[str]] = {
    "NVDA": ["nvidia", "jensen huang"],
    "AAPL": ["apple", "iphone", "tim cook"],
    "MSFT": ["microsoft", "satya nadella", "azure"],
    "GOOGL": ["google", "alphabet", "sundar pichai"],
    "GOOG": ["google", "alphabet"],
    "AMZN": ["amazon", "aws", "andy jassy"],
    "META": ["meta platforms", "facebook", "instagram", "zuckerberg"],
    "TSLA": ["tesla", "elon musk"],
    "AMD": ["advanced micro devices", "lisa su"],
    "INTC": ["intel"],
    "AVGO": ["broadcom"],
    "TSM": ["taiwan semiconductor", "tsmc"],
    "ARM": ["arm holdings"],
    "QCOM": ["qualcomm"],
    "MU": ["micron"],
    "ASML": ["asml"],
    "AMAT": ["applied materials"],
    "LRCX": ["lam research"],
    "KLAC": ["kla"],
    "MRVL": ["marvell"],
    "DELL": ["dell technologies"],
    "SMCI": ["super micro", "supermicro"],
    "ANET": ["arista"],
    "NFLX": ["netflix"],
    "DIS": ["disney"],
    "BA": ["boeing"],
    "JPM": ["jpmorgan", "jp morgan"],
    "GS": ["goldman sachs"],
    "BAC": ["bank of america"],
    "WFC": ["wells fargo"],
    "C": ["citigroup"],
    "XOM": ["exxon"],
    "CVX": ["chevron"],
    "F": ["ford motor"],
    "GM": ["general motors"],
    "WMT": ["walmart"],
    "COST": ["costco"],
    "TGT": ["target corporation"],
    "PYPL": ["paypal"],
    "SQ": ["block inc", "square inc"],
    "COIN": ["coinbase"],
    "CRM": ["salesforce"],
    "ORCL": ["oracle"],
    "ADBE": ["adobe"],
    "PLTR": ["palantir"],
    "SNOW": ["snowflake"],
    "UBER": ["uber technologies"],
    "ABNB": ["airbnb"],
    "BABA": ["alibaba"],
    "BIDU": ["baidu"],
    "PDD": ["pinduoduo", "temu"],
}

# Sector peer baskets — used to flag "related_sector" mentions. A ticker's
# peers should NOT include itself.
SECTOR_PEERS: dict[str, list[str]] = {
    # Semis
    "NVDA": [
        "AMD", "AVGO", "INTC", "TSM", "ARM", "QCOM", "MU", "MRVL",
        "ASML", "AMAT", "LRCX", "KLAC", "DELL", "SMCI", "ANET",
    ],
    "AMD": ["NVDA", "INTC", "AVGO", "TSM", "ARM", "QCOM", "MU"],
    "AVGO": ["NVDA", "AMD", "QCOM", "MRVL", "TSM"],
    "INTC": ["NVDA", "AMD", "AVGO", "TSM", "ARM", "QCOM"],
    "TSM": ["NVDA", "AMD", "ASML", "AMAT", "LRCX", "KLAC"],
    "QCOM": ["NVDA", "AVGO", "ARM", "MRVL", "INTC"],
    "MU": ["NVDA", "INTC", "AMD"],
    "ARM": ["NVDA", "QCOM", "AMD", "INTC"],
    # Mega-cap tech / hyperscalers
    "AAPL": ["MSFT", "GOOGL", "AMZN", "META", "TSLA", "QCOM", "AVGO"],
    "MSFT": ["GOOGL", "AAPL", "AMZN", "META", "ORCL", "CRM", "NVDA"],
    "GOOGL": ["MSFT", "AAPL", "AMZN", "META", "NVDA"],
    "GOOG": ["MSFT", "AAPL", "AMZN", "META", "NVDA"],
    "AMZN": ["MSFT", "GOOGL", "WMT", "META", "TGT", "COST"],
    "META": ["GOOGL", "MSFT", "AAPL", "AMZN", "SNAP", "PINS"],
    "TSLA": ["F", "GM", "RIVN", "LCID", "NIO"],
    # Software
    "CRM": ["MSFT", "ORCL", "ADBE", "SNOW", "WDAY"],
    "ORCL": ["MSFT", "CRM", "SAP", "IBM"],
    "ADBE": ["MSFT", "CRM", "INTU"],
    "PLTR": ["NOW", "SNOW", "MDB", "CRM"],
    "SNOW": ["MDB", "DDOG", "PLTR", "CRM"],
    # Finance
    "JPM": ["GS", "BAC", "WFC", "C", "MS"],
    "GS": ["JPM", "MS", "BAC", "WFC"],
    "BAC": ["JPM", "WFC", "C", "GS"],
    "WFC": ["JPM", "BAC", "C"],
    # Energy
    "XOM": ["CVX", "COP", "BP", "SHEL"],
    "CVX": ["XOM", "COP", "BP", "SHEL"],
    # Autos
    "F": ["GM", "TSLA", "STLA"],
    "GM": ["F", "TSLA", "STLA"],
    # Retail
    "WMT": ["TGT", "COST", "AMZN"],
    "TGT": ["WMT", "COST", "AMZN"],
    "COST": ["WMT", "TGT"],
    # Crypto / fintech
    "COIN": ["SQ", "PYPL", "HOOD"],
    "PYPL": ["SQ", "COIN", "V", "MA"],
    "SQ": ["PYPL", "COIN"],
}


def aliases_for(ticker: str) -> list[str]:
    """Return the lowercased alias list for ``ticker`` (always includes the bare ticker)."""
    t = (ticker or "").upper()
    base = [t.lower()]
    base.extend(a.lower() for a in TICKER_ALIASES.get(t, []))
    return base


def peers_for(ticker: str) -> list[str]:
    """Return sector-peer tickers (uppercase) excluding the ticker itself."""
    t = (ticker or "").upper()
    return [p for p in SECTOR_PEERS.get(t, []) if p != t]


# Macro keyword set. Lowercased; matched as substrings on word boundaries are not
# enforced because financial headlines are noisy ("rates" inside "rateshare" is rare).
MACRO_KEYWORDS: frozenset[str] = frozenset(
    {
        "fed",
        "fomc",
        "federal reserve",
        "interest rate",
        "rate hike",
        "rate cut",
        "powell",
        "cpi",
        "ppi",
        "inflation",
        "jobs report",
        "payrolls",
        "unemployment",
        "treasury yield",
        "yields",
        "10-year",
        "dollar index",
        "dxy",
        "oil prices",
        "crude oil",
        "vix",
        "s&p 500",
        "nasdaq",
        "dow jones",
        "spx",
        "qqq",
        "russell 2000",
        "recession",
        "china tariff",
        "tariff",
        "geopolit",
    }
)
