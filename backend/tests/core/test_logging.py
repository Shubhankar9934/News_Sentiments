from pathlib import Path

from app.core.logging import _daily_log_path, configure_logging, get_logger


def test_configure_logging_writes_daily_txt(tmp_path: Path) -> None:
    log_file = configure_logging(
        json_logs=False,
        log_to_file=True,
        log_dir=tmp_path,
    )
    assert log_file is not None
    assert log_file.parent == tmp_path
    assert log_file.suffix == ".txt"
    assert log_file.name.startswith("backend_")

    logger = get_logger("tests.core.test_logging")
    logger.info("test.event", detail="analysis friendly")

    content = log_file.read_text(encoding="utf-8")
    assert "test.event" in content
    assert "analysis friendly" in content
    assert "T" in content  # ISO timestamp marker


def test_daily_log_path_uses_utc_date(tmp_path: Path) -> None:
    path = _daily_log_path(tmp_path)
    assert path.parent == tmp_path
    assert len(path.stem.split("_")) == 2
