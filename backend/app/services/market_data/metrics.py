"""Prometheus counters for the live market-data layer.

All metrics live behind the standard ``prometheus_client`` registry that
the ``/metrics`` endpoint exposes. Keep names short; tag dimensions are
limited to ticker/side/result so cardinality stays bounded.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge

# --------------------------------------------------------------------------
# Opportunity generation
# --------------------------------------------------------------------------
opps_generated_total = Counter(
    "market_data_opps_generated_total",
    "Number of Reverse BWB opportunities produced (post-filter) per cycle.",
    labelnames=("ticker", "side"),
)

opps_persisted_total = Counter(
    "market_data_opps_persisted_total",
    "Number of opportunity rows written to the live table per cycle.",
    labelnames=("ticker", "side"),
)

opps_history_appended_total = Counter(
    "market_data_opps_history_appended_total",
    "Number of opportunity rows appended to the append-only history.",
    labelnames=("ticker", "side"),
)

opportunity_version_total = Counter(
    "market_data_opportunity_version_total",
    "Number of new opportunity_version UUIDs minted (= recalc cycles).",
    labelnames=("ticker", "trigger"),
)

# --------------------------------------------------------------------------
# WhatIf / margin engine
# --------------------------------------------------------------------------
whatif_calls_total = Counter(
    "market_data_whatif_calls_total",
    "IBKR WhatIf round-trip attempts.",
    labelnames=("result",),  # ok | error | budget_exhausted
)

# --------------------------------------------------------------------------
# WebSocket fanout
# --------------------------------------------------------------------------
ws_messages_total = Counter(
    "market_data_ws_messages_total",
    "WebSocket messages dispatched.",
    labelnames=("type",),  # tick | opportunity_version
)

ws_active_clients = Gauge(
    "market_data_ws_active_clients",
    "Number of currently-connected market data WebSocket clients.",
)

ws_dropped_overflow_total = Counter(
    "market_data_ws_dropped_overflow_total",
    "WebSocket messages dropped because a subscriber's queue was full.",
)
