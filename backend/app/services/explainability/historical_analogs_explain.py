"""Historical-analog explainability block.

Reads ``_pipeline_meta.historical_analogs`` (rows enriched by the
:mod:`app.services.analogs.setup_simulator`) and
``_pipeline_meta.historical_analog_aggregates`` into the report panel
schema.
"""

from __future__ import annotations

from typing import Any

from app.services.dashboard.schemas import (
    HistoricalAnalogAggregates,
    HistoricalAnalogMatch,
    HistoricalAnalogsExplain,
)


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def build_historical_analogs_explain(
    *,
    ticker: str,  # noqa: ARG001
    report: dict[str, Any],
) -> HistoricalAnalogsExplain | None:
    meta = _safe_dict(report.get("_pipeline_meta") if isinstance(report, dict) else None)
    rows = meta.get("historical_analogs")
    aggregates_dict = _safe_dict(meta.get("historical_analog_aggregates"))

    if not isinstance(rows, list) or not rows:
        return None

    matches: list[HistoricalAnalogMatch] = []
    for row in rows[:10]:
        if not isinstance(row, dict):
            continue
        stats = _safe_dict(row.get("setup_outcome_stats"))
        try:
            matches.append(
                HistoricalAnalogMatch(
                    headline=row.get("headline"),
                    published_at=(
                        str(row["published_at"])[:19] if row.get("published_at") else None
                    ),
                    sentiment_score=(
                        float(row["sentiment_score"])
                        if isinstance(row.get("sentiment_score"), (int, float))
                        else None
                    ),
                    impact_score=(
                        float(row["impact_score"])
                        if isinstance(row.get("impact_score"), (int, float))
                        else None
                    ),
                    match_reason=row.get("match_reason"),
                    match_score=(
                        float(row["match_score"])
                        if isinstance(row.get("match_score"), (int, float))
                        else None
                    ),
                    forward_return_pct=stats.get("forward_return_pct"),
                    body_touched=stats.get("body_touched"),
                    credit_retained_pct=stats.get("credit_retained"),
                )
            )
        except Exception:
            continue

    try:
        aggregates = HistoricalAnalogAggregates.model_validate(
            {
                "n_setups": int(aggregates_dict.get("n_setups") or 0),
                "win_rate": aggregates_dict.get("win_rate"),
                "avg_credit_retained": aggregates_dict.get("avg_credit_retained"),
                "max_loss_frequency": aggregates_dict.get("max_loss_frequency"),
                "avg_forward_return_pct": aggregates_dict.get("avg_forward_return_pct"),
                "p_touch_body": aggregates_dict.get("p_touch_body"),
            }
        )
    except Exception:
        aggregates = HistoricalAnalogAggregates()

    warning = None
    if aggregates.n_setups < 8:
        warning = (
            f"Only {aggregates.n_setups} forward-projectable analog setups — "
            "aggregate win-rate is directional rather than statistical."
        )

    return HistoricalAnalogsExplain(
        matches=matches,
        aggregates=aggregates,
        lookback_window=None,
        sample_size_warning=warning,
    )
