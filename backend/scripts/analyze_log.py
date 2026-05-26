"""Quick log analysis helper."""

from __future__ import annotations

import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

SKIP = (
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "BEGIN",
    "COMMIT",
    "ROLLBACK",
    "[",
    "select ",
    "show ",
    "HTTP Request",
)


def analyze(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    clean = re.sub(r"\x1b\[[0-9;]*m", "", text)
    lines = [line for line in clean.splitlines() if line.strip()]

    ts_re = re.compile(r"^(\d{4}-\d{2}-\d{2}T[\d:.]+Z)\s+\[(\w+)\s*\]\s+(\S+)")
    events: list[tuple[str, str, str, str]] = []
    for line in lines:
        match = ts_re.match(line)
        if match:
            events.append((match.group(1), match.group(2).strip(), match.group(3).strip(), line))

    app = [event for event in events if not any(event[2].startswith(prefix) for prefix in SKIP)]

    print("=== SUMMARY ===")
    print(f"Total lines: {len(lines)} | Parsed events: {len(events)} | App events: {len(app)}")
    if events:
        print(f"Time range: {events[0][0]} -> {events[-1][0]}")
    print(f"Levels: {dict(Counter(event[1] for event in events))}")
    print(f"Server restarts: {sum(1 for event in app if event[2] == 'logging.file_enabled')}")

    warn_err = [event for event in app if event[1] in ("warning", "error")]
    print(f"\n=== WARNINGS/ERRORS ({len(warn_err)}) ===")
    for event in warn_err:
        print(event[3][:320])

    print("\n=== WATCHLIST / PIPELINE ===")
    keys = (
        "watchlist.ticker",
        "pipeline.start",
        "pipeline.complete",
        "dil.start",
        "dil.complete",
        "collector.source_failed",
        "claude.report_json",
    )
    for event in app:
        if any(key in event[2] for key in keys):
            print(event[3].split(" correlation_id")[0][:220])

    tickers = re.findall(r"ticker=(\w+)", clean)
    print("\n=== TICKERS ===", dict(Counter(tickers)))

    llm = [event for event in app if event[2] == "dil.llm_call"]
    models = re.findall(r"model=(\w+)", "\n".join(event[3] for event in llm))
    elapsed = [int(value) for value in re.findall(r"elapsed_ms=(\d+)", "\n".join(event[3] for event in llm))]
    retries = sum(int(value) for value in re.findall(r"rate_limit_retries=(\d+)", "\n".join(event[3] for event in llm)))

    print("\n=== LLM ===")
    print(f"Calls: {len(llm)} | Models: {dict(Counter(models))}")
    if elapsed:
        print(f"Latency ms: min={min(elapsed)} max={max(elapsed)} avg={sum(elapsed) // len(elapsed)}")
    print(f"Rate limit retries (sum): {retries}")

    print("\n=== RESILIENCE ===")
    resilience_keys = (
        "dil.resilience.retry.skip",
        "dil.resilience.retry.wait",
        "dil.desk.failover",
        "dil.desk.provider_failed",
        "dil.council.provider_failed",
        "dil.assessment.provider_failed",
        "dil.debate2.desk_failed",
        "dil.debate1.desk_failed",
        "dil.llm_error",
        "dil.resilience.routing.invalid_provider",
    )
    for key in resilience_keys:
        count = sum(1 for event in app if event[2] == key)
        if count:
            print(f"  {key}: {count}")

    print("\n=== GROQ / DEEPSEEK FAILOVERS ===")
    for event in app:
        if "failover" in event[2] and ("groq" in event[3].lower() or "deepseek" in event[3].lower()):
            print(event[3][:280])

    print("\n=== DIL OUTCOMES ===")
    for event in app:
        if event[2] == "dil.complete":
            print(event[3][:350])

    # per-run durations
    fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
    print("\n=== RUN DURATIONS ===")
    starts = [event for event in app if event[2] == "watchlist.ticker.start"]
    for start in starts:
        cid = re.search(r"correlation_id=(\S+)", start[3])
        if not cid:
            continue
        correlation = cid.group(1)
        related = [event for event in app if correlation in event[3]]
        end = next((event for event in related if event[2] == "watchlist.ticker.completed"), None)
        pipe_start = next((event for event in related if event[2] == "pipeline.start"), None)
        pipe_end = next((event for event in related if event[2] == "pipeline.complete"), None)
        dil_start = next((event for event in related if event[2] == "dil.start"), None)
        dil_end = next((event for event in related if event[2] == "dil.complete"), None)
        ticker = re.search(r"ticker=(\w+)", start[3])
        label = ticker.group(1) if ticker else "?"
        if end:
            total = (datetime.strptime(end[0], fmt) - datetime.strptime(start[0], fmt)).total_seconds()
            print(f"{label}: total={total/60:.1f}m", end="")
            if pipe_start and pipe_end:
                pipe = (datetime.strptime(pipe_end[0], fmt) - datetime.strptime(pipe_start[0], fmt)).total_seconds()
                print(f" pipeline={pipe/60:.1f}m", end="")
            if dil_start and dil_end:
                dil = (datetime.strptime(dil_end[0], fmt) - datetime.strptime(dil_start[0], fmt)).total_seconds()
                print(f" dil={dil/60:.1f}m", end="")
            print()

    print("\n=== TOP APP EVENTS ===")
    for name, count in Counter(event[2] for event in app).most_common(20):
        print(f"  {count:4d}  {name}")


if __name__ == "__main__":
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("logs/backend_2026-05-24.txt")
    analyze(log_path)
