"""Technical indicators from OHLCV series."""

from __future__ import annotations

from typing import Any


def _closes(series: list[dict[str, Any]]) -> list[float]:
    return [float(b["c"]) for b in series if b.get("c") is not None]


def _ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
    return round(ema, 4)


def _rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _atr(series: list[dict[str, Any]], period: int = 14) -> float | None:
    if len(series) < period + 1:
        return None
    trs: list[float] = []
    for i in range(1, len(series)):
        h, l, pc = series[i].get("h"), series[i].get("l"), series[i - 1].get("c")
        if h is None or l is None or pc is None:
            continue
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
    if len(trs) < period:
        return None
    return round(sum(trs[-period:]) / period, 4)


def build_technical_context(
    ohlcv_series: list[dict[str, Any]],
    price_snapshot: dict[str, Any],
) -> dict[str, Any]:
    closes = _closes(ohlcv_series)
    if len(closes) < 2:
        return {"trend": "unknown", "note": "insufficient price history"}

    last = closes[-1]
    sma20 = sum(closes[-20:]) / min(20, len(closes)) if closes else last
    trend = "uptrend" if last > sma20 * 1.01 else "downtrend" if last < sma20 * 0.99 else "range_bound"

    window = ohlcv_series[-20:] if len(ohlcv_series) >= 20 else ohlcv_series
    support = min(float(b.get("l", last)) for b in window)
    resistance = max(float(b.get("h", last)) for b in window)

    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd = round(ema12 - ema26, 4) if ema12 is not None and ema26 is not None else None

    return {
        "trend": trend,
        "last_close": last,
        "sma_20": round(sma20, 4),
        "support": round(support, 4),
        "resistance": round(resistance, 4),
        "rsi_14": _rsi(closes),
        "macd": macd,
        "atr_14": _atr(ohlcv_series),
        "last_session_change_pct": price_snapshot.get("last_session_change_pct"),
        "volume_vs_avg": price_snapshot.get("volume_vs_avg"),
    }
