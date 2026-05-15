"""Domain constants (ported from legacy pipeline)."""

SOURCE_RELIABILITY: dict[str, int] = {
    "SEC Filing": 98,
    "Reuters": 92,
    "Bloomberg": 91,
    "WSJ": 88,
    "Financial Times": 87,
    "AP": 86,
    "CNBC": 78,
    "Yahoo Finance": 72,
    "MarketWatch": 70,
    "Seeking Alpha": 58,
    "Reddit": 35,
    "Twitter/X": 30,
}

EVENT_IMPACT_WEIGHTS: dict[str, float] = {
    "Earnings": 1.0,
    "Regulation": 0.9,
    "Supply Chain": 0.85,
    "Macro": 0.8,
    "Partnership": 0.7,
    "Product": 0.65,
    "Analyst": 0.5,
}

API_VERSION = "4.0.0"
