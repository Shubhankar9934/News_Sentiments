"""Pipeline data audit writer.

Writes a human-readable snapshot of every pipeline stage to disk so
developers can inspect exactly what data was used at each step of a
Run Analysis call.

Folder layout::

    {audit_path}/
      {TICKER}/
        {YYYY-MM-DD_HH-MM-SS}_{run_id[:8]}/
          00_raw_articles.txt
          01_cleaned_articles.txt
          02_sentiment.txt
          03_events.txt
          04_market_price.txt       ← Polygon OHLCV vs IBKR live comparison
          05_impact_scores.txt
          06_narrative_clusters.txt
          07_claude_report.txt
          08_options_intelligence.txt
          09_opportunities.txt      ← source label (placeholder / ibkr_live)
          10_historical_analogs.txt
          11_executive_summary.txt
          pipeline_summary.txt      ← single-file high-level overview

Writes are fire-and-forget: any IO error is logged at DEBUG level and
never propagates to the caller so the pipeline is never broken by disk
issues.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_SEPARATOR = "=" * 80


def _dump(value: Any, indent: int = 2) -> str:
    """Best-effort JSON serialisation with a plain-string fallback."""
    try:
        return json.dumps(value, indent=indent, default=str, ensure_ascii=False)
    except Exception:
        return str(value)


def _header(title: str, run_id: str, ticker: str, ts: str) -> str:
    return (
        f"{_SEPARATOR}\n"
        f"PIPELINE AUDIT — {title}\n"
        f"Ticker : {ticker}\n"
        f"Run ID : {run_id}\n"
        f"Time   : {ts}\n"
        f"{_SEPARATOR}\n\n"
    )


class PipelineAuditWriter:
    """Writes pipeline stage data to a per-run folder.

    Construction is cheap. Call :meth:`write` after each pipeline stage.
    Call :meth:`write_summary` at the end of the run.

    All methods are synchronous and non-blocking from the caller's
    perspective — any filesystem error is silently swallowed.
    """

    def __init__(
        self,
        audit_path: str,
        ticker: str,
        run_id: str,
    ) -> None:
        ts = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
        short_id = run_id[:8]
        self._ticker = ticker.upper()
        self._run_id = run_id
        self._ts = ts
        self._enabled = True

        try:
            folder = Path(audit_path) / self._ticker / f"{ts}_{short_id}"
            folder.mkdir(parents=True, exist_ok=True)
            self._folder: Path | None = folder
            log.debug("pipeline_audit.folder_created path=%s", folder)
        except Exception as exc:
            log.debug("pipeline_audit.folder_failed error=%s", exc)
            self._folder = None
            self._enabled = False

    # ------------------------------------------------------------------ write

    def write(self, filename: str, title: str, data: Any) -> None:
        """Write *data* to *filename* under the audit folder.

        *data* can be any JSON-serialisable object or a plain string.
        """
        if not self._enabled or self._folder is None:
            return
        try:
            header = _header(title, self._run_id, self._ticker, self._ts)
            body = data if isinstance(data, str) else _dump(data)
            (self._folder / filename).write_text(
                header + body + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            log.debug("pipeline_audit.write_failed file=%s error=%s", filename, exc)

    def write_summary(self, stages: dict[str, Any]) -> None:
        """Write a high-level summary of all stages to pipeline_summary.txt."""
        if not self._enabled or self._folder is None:
            return
        try:
            lines: list[str] = [
                _SEPARATOR,
                "PIPELINE SUMMARY",
                f"Ticker : {self._ticker}",
                f"Run ID : {self._run_id}",
                f"Time   : {self._ts}",
                _SEPARATOR,
                "",
            ]
            for stage, info in stages.items():
                lines.append(f"[{stage}]")
                if isinstance(info, dict):
                    for k, v in info.items():
                        lines.append(f"  {k}: {v}")
                else:
                    lines.append(f"  {info}")
                lines.append("")
            (self._folder / "pipeline_summary.txt").write_text(
                "\n".join(lines) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            log.debug("pipeline_audit.summary_failed error=%s", exc)

    @property
    def folder(self) -> str | None:
        """Absolute path to the run folder (None if creation failed)."""
        if self._folder is None:
            return None
        return str(self._folder.resolve())


def make_audit_writer(
    settings_audit_enabled: bool,
    settings_audit_path: str,
    ticker: str,
    run_id: str,
) -> PipelineAuditWriter:
    """Factory that returns a disabled no-op writer when auditing is off."""
    writer = PipelineAuditWriter(
        audit_path=settings_audit_path,
        ticker=ticker,
        run_id=run_id,
    )
    if not settings_audit_enabled:
        writer._enabled = False  # noqa: SLF001
    return writer
