"""Break down DIL phase duration and LLM call counts per run."""

from __future__ import annotations

import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

FMT = "%Y-%m-%dT%H:%M:%S.%fZ"
TS = re.compile(r"^(\d{4}-\d{2}-\d{2}T[\d:.]+Z)")

RUNS = {
    "QQQ (run 1, pre-fix)": "544b6145-c618-4893-a297-b8a83882926c",
    "IWM (run 2, post-fix)": "bcb24543-a36f-461e-aea8-ea8c96023ac2",
}


def _ts(line: str) -> datetime | None:
    match = TS.match(line)
    if not match:
        return None
    return datetime.strptime(match.group(1), FMT)


def _between(lines: list[str], start: datetime, end: datetime) -> list[str]:
    out: list[str] = []
    for line in lines:
        t = _ts(line)
        if t and start <= t <= end:
            out.append(line)
    return out


def analyze_run(label: str, cid: str, clean: str) -> None:
    lines = [line for line in clean.splitlines() if cid in line]
    dil_start_line = next(line for line in lines if "dil.start" in line)
    dil_end_line = next(line for line in lines if "dil.complete" in line)
    t0 = _ts(dil_start_line)
    t1 = _ts(dil_end_line)
    assert t0 and t1
    dil_sec = (t1 - t0).total_seconds()

    llm_calls = [line for line in lines if "dil.llm_call" in line]
    models = re.findall(r"model=(\w+)", "\n".join(llm_calls))
    elapsed = [int(x) for x in re.findall(r"elapsed_ms=(\d+)", "\n".join(llm_calls))]
    wait_ms = [
        int(x)
        for x in re.findall(
            r"wait_ms=(\d+)", "\n".join(l for l in lines if "concurrency.wait" in l)
        )
    ]

    # Phase boundaries from logs
    markers = {
        "assessment.start": next((l for l in lines if "dil.assessment.start" in l), None),
        "assessment.complete": next((l for l in lines if "dil.assessment.complete" in l), None),
        "council.start": next((l for l in lines if "dil.council.start" in l), None),
        "council.complete": next((l for l in lines if "dil.council.complete" in l), None),
    }

    print("=" * 68)
    print(label)
    print("=" * 68)
    print(f"DIL wall clock: {dil_sec / 60:.1f} min ({dil_sec:.0f}s)")
    print(f"Total LLM calls logged: {len(llm_calls)}")
    print(f"By provider: {dict(Counter(models))}")
    if elapsed:
        print(
            f"Sum of per-call latency: {sum(elapsed) / 1000:.0f}s "
            f"(avg {sum(elapsed) // len(elapsed)}ms, max {max(elapsed)}ms)"
        )
    print(
        f"Concurrency queue waits: {len(wait_ms)} events, "
        f"{sum(wait_ms) / 1000:.0f}s total blocked"
    )

    # Estimate stage splits using timestamps
    assessment_start = _ts(markers["assessment.start"]) if markers["assessment.start"] else None
    assessment_end = _ts(markers["assessment.complete"]) if markers["assessment.complete"] else None
    council_start = _ts(markers["council.start"]) if markers["council.start"] else None
    council_end = _ts(markers["council.complete"]) if markers["council.complete"] else None

    if assessment_start and assessment_end:
        desk_sec = (assessment_start - t0).total_seconds()
        assess_sec = (assessment_end - assessment_start).total_seconds()
        print(f"\nStage wall clock (from log markers):")
        print(f"  1. Desk analysis:     {desk_sec / 60:.1f} min ({desk_sec:.0f}s)")
        print(f"  2. Assessment team:   {assess_sec / 60:.1f} min ({assess_sec:.0f}s)")
        if council_start and council_end:
            council_sec = (council_end - council_start).total_seconds()
            debate_sec = (council_start - assessment_end).total_seconds()
            print(f"  3. Desk debate:       {debate_sec / 60:.1f} min ({debate_sec:.0f}s)")
            print(f"  4. Decision council:  {council_sec / 60:.1f} min ({council_sec:.0f}s)")

    # Calls per stage (approximate by timestamp windows)
    if assessment_start:
        desk_calls = _between(llm_calls, t0, assessment_start)
        assess_calls = (
            _between(llm_calls, assessment_start, assessment_end)
            if assessment_end
            else []
        )
        debate_calls = (
            _between(llm_calls, assessment_end, council_start)
            if assessment_end and council_start
            else []
        )
        council_calls = (
            _between(llm_calls, council_start, council_end)
            if council_start and council_end
            else []
        )
        print("\nLLM calls by stage (timestamp windows):")
        print(f"  Desk analysis:     {len(desk_calls)}")
        print(f"  Assessment team:   {len(assess_calls)}")
        print(f"  Desk debate:       {len(debate_calls)}")
        print(f"  Decision council:  {len(council_calls)}")
        accounted = len(desk_calls) + len(assess_calls) + len(debate_calls) + len(council_calls)
        print(f"  Accounted total:   {accounted} / {len(llm_calls)}")

    # Why slow
    overhead = dil_sec - (sum(elapsed) / 1000 if elapsed else 0) - (sum(wait_ms) / 1000)
    print("\nWhere the time goes:")
    print(f"  Actual LLM response time (parallel): ~{sum(elapsed) / 1000:.0f}s summed")
    print(f"  Concurrency queue waits:             ~{sum(wait_ms) / 1000:.0f}s")
    print(
        f"  Orchestration / DB / parsing / gaps: ~{max(0, overhead):.0f}s "
        "(sequential stages + 5-slot concurrency cap)"
    )

    print("\nCall timeline (30s buckets from dil.start):")
    buckets: Counter[int] = Counter()
    for line in llm_calls:
        t = _ts(line)
        if not t:
            continue
        bucket = int((t - t0).total_seconds() // 30) * 30
        buckets[bucket] += 1
    for sec in sorted(buckets):
        print(f"  +{sec:3d}s: {buckets[sec]:2d} calls {'#' * buckets[sec]}")
    print()


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("logs/backend_2026-05-24.txt")
    clean = re.sub(r"\x1b\[[0-9;]*m", "", path.read_text(encoding="utf-8"))
    for label, cid in RUNS.items():
        analyze_run(label, cid, clean)


if __name__ == "__main__":
    main()
