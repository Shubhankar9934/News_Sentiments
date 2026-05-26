"""Structured logging setup."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import structlog

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _resolve_log_dir(log_dir: str | Path) -> Path:
    path = Path(log_dir)
    if not path.is_absolute():
        path = BACKEND_ROOT / path
    return path


def _daily_log_path(log_dir: Path) -> Path:
    date_stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return log_dir / f"backend_{date_stamp}.txt"


def configure_logging(
    *,
    json_logs: bool = True,
    log_to_file: bool = True,
    log_dir: str | Path = "logs",
) -> Path | None:
    """Configure structlog with console output and optional daily file logs."""
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    console_renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer()
    )
    file_renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(colors=False)

    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=console_renderer,
        foreign_pre_chain=shared_processors,
    )
    file_formatter = structlog.stdlib.ProcessorFormatter(
        processor=file_renderer,
        foreign_pre_chain=shared_processors,
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    # Keep third-party chatter out of analysis logs; app code uses structlog.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    root.addHandler(console_handler)

    log_file: Path | None = None
    if log_to_file:
        resolved_dir = _resolve_log_dir(log_dir)
        resolved_dir.mkdir(parents=True, exist_ok=True)
        log_file = _daily_log_path(resolved_dir)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(file_formatter)
        root.addHandler(file_handler)

    structlog.configure(
        processors=shared_processors
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return log_file


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
