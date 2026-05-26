"""Project the current Reverse-BWB structure onto each historical analog (Phase 7).

Given a list of analog rows (each containing a published_at + close
price for the analog date) and the *current* Reverse-BWB structure
(body_strike, wing_width_pct, credit, dte), this simulator pulls
forward-bar OHLCV from the prices table for the period after each
analog and computes:

* did the underlying touch the short body during DTE?
* did the underlying touch either wing?
* what was the realised forward return at DTE?
* what fraction of the credit would have been retained?

Aggregates across all matches into the win-rate / max-loss-frequency /
average-credit-retained metrics surfaced on the report.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger(__name__)


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value)
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[: len(s) if "+" in s or "T" in s else 10], fmt)
        except Exception:  # noqa: BLE001
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


async def _forward_path(
    session: AsyncSession,
    ticker: str,
    start: datetime,
    dte: int,
) -> list[float]:
    """Fetch closes for the next ``dte`` trading days after ``start`` (inclusive)."""

    if dte <= 0:
        return []
    end = start + timedelta(days=max(dte * 2, 4))  # over-collect; trading days < calendar days
    q = text(
        """
        SELECT close
        FROM ohlcv_bars
        WHERE ticker = :ticker
          AND timestamp >= :start
          AND timestamp <= :end
          AND timeframe = '1d'
        ORDER BY timestamp ASC
        LIMIT :limit
        """
    )
    result = await session.execute(
        q,
        {
            "ticker": ticker,
            "start": start,
            "end": end,
            "limit": max(dte + 1, 4),
        },
    )
    return [float(r[0]) for r in result.fetchall() if r[0] is not None]


def _scale_strikes_to_analog(
    *,
    analog_close: float,
    current_spot: float,
    current_body: float,
    current_wing_dollars: float,
) -> tuple[float, float, float]:
    """Scale the current dollar-defined structure to the analog price level.

    Returns ``(body, lower_wing, upper_wing)`` rebased to the analog's
    starting price so the body sits proportionally the same distance
    above/below spot as it does today.
    """

    if current_spot <= 0:
        return (analog_close, analog_close - current_wing_dollars, analog_close + current_wing_dollars)
    body_offset_pct = (current_body - current_spot) / current_spot
    wing_pct = current_wing_dollars / current_spot
    body = analog_close * (1.0 + body_offset_pct)
    return (
        body,
        body - analog_close * wing_pct,
        body + analog_close * wing_pct,
    )


def _simulate_one_analog(
    *,
    analog_close: float,
    forward_path: list[float],
    current_spot: float,
    current_body: float,
    current_wing_dollars: float,
    credit: float,
) -> dict[str, Any]:
    """Project current structure onto a single analog's forward path."""

    if analog_close <= 0 or not forward_path:
        return {
            "valid": False,
            "body_touched": None,
            "wing_touched": None,
            "credit_retained": None,
            "forward_return_pct": None,
        }

    body, wing_lo, wing_hi = _scale_strikes_to_analog(
        analog_close=analog_close,
        current_spot=current_spot,
        current_body=current_body,
        current_wing_dollars=current_wing_dollars,
    )

    # Reverse BWB max-loss region = the body zone (between wings). We
    # distinguish *path touch* from *terminal landing*:
    #   - body_touched: price approached the body strike within ±0.4
    #     wing-widths at any time during DTE.
    #   - wing_touched: TERMINAL price landed inside the body zone
    #     (between the wing strikes), where max loss crystalises.
    proximity = current_wing_dollars * 0.4
    body_touched = False
    for px in forward_path:
        if abs(px - body) <= proximity:
            body_touched = True
            break

    terminal = forward_path[-1]
    wing_touched = bool(wing_lo < terminal < wing_hi)
    forward_return = (terminal - analog_close) / analog_close * 100.0

    # Credit retained heuristic: keep full credit if neither body nor wing
    # were touched; partial credit if body touched but not wing; zero if
    # wing touched (max loss).
    if wing_touched:
        credit_retained = 0.0
    elif body_touched:
        credit_retained = max(0.0, credit * 0.55)
    else:
        credit_retained = credit

    return {
        "valid": True,
        "body_touched": body_touched,
        "wing_touched": wing_touched,
        "credit_retained": round(credit_retained / max(credit, 1e-9) * 100.0, 1),
        "forward_return_pct": round(forward_return, 3),
    }


async def simulate_analog_setups(
    *,
    session: AsyncSession,
    ticker: str,
    analogs: list[dict[str, Any]],
    current_spot: float,
    current_body: float,
    wing_width_pct: float,
    credit: float,
    dte: int,
) -> dict[str, Any]:
    """Project the current structure onto every analog and aggregate."""

    if not analogs or current_spot <= 0 or wing_width_pct <= 0 or dte <= 0:
        return {
            "matches": [],
            "aggregates": {
                "n_setups": 0,
                "win_rate": None,
                "avg_credit_retained": None,
                "max_loss_frequency": None,
                "avg_forward_return_pct": None,
                "p_touch_body": None,
            },
        }

    current_wing_dollars = current_spot * (wing_width_pct / 100.0)

    enriched: list[dict[str, Any]] = []
    valid_results: list[dict[str, Any]] = []

    for row in analogs[:25]:  # cap total simulation work
        published = _parse_dt(row.get("published_at"))
        analog_close = row.get("close")
        if published is None or analog_close is None:
            enriched.append({**row, "setup_outcome_stats": None})
            continue
        forward_path: list[float] = []
        try:
            forward_path = await _forward_path(session, ticker, published, dte)
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("analog.forward_path_failed", error=str(exc))

        outcome = _simulate_one_analog(
            analog_close=float(analog_close),
            forward_path=forward_path,
            current_spot=current_spot,
            current_body=current_body,
            current_wing_dollars=current_wing_dollars,
            credit=credit,
        )
        enriched.append({**row, "setup_outcome_stats": outcome})
        if outcome["valid"]:
            valid_results.append(outcome)

    n = len(valid_results)
    if n == 0:
        return {
            "matches": enriched,
            "aggregates": {
                "n_setups": 0,
                "win_rate": None,
                "avg_credit_retained": None,
                "max_loss_frequency": None,
                "avg_forward_return_pct": None,
                "p_touch_body": None,
            },
        }

    wins = sum(1 for o in valid_results if not o["wing_touched"])
    losses = sum(1 for o in valid_results if o["wing_touched"])
    body_touches = sum(1 for o in valid_results if o["body_touched"])
    avg_credit_retained = sum(o["credit_retained"] for o in valid_results) / n
    avg_forward_return = sum(o["forward_return_pct"] for o in valid_results) / n

    return {
        "matches": enriched,
        "aggregates": {
            "n_setups": n,
            "win_rate": round(wins / n, 3),
            "avg_credit_retained": round(avg_credit_retained, 2),
            "max_loss_frequency": round(losses / n, 3),
            "avg_forward_return_pct": round(avg_forward_return, 3),
            "p_touch_body": round(body_touches / n, 3),
        },
    }
