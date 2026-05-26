/**
 * Sequential / pooled orchestrator for the "Run All" button.
 *
 * The DIL pipeline involves up to 5 LLM providers per ticker so firing 12
 * tickers in parallel would torch the rate-limits. This hook keeps the
 * concurrency bounded (default 2), tracks per-ticker progress in local
 * state, and surfaces a `cancel` to abort the queue mid-flight.
 */

import { useCallback, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { ALL_WATCHLIST_TICKERS } from "@/config/watchlist";
import { extractDashboardSummary } from "@/lib/extractDashboardSummary";
import {
  researchReportSchema,
  type ResearchReport,
  type TickerSummaryRow,
} from "@/types/schemas";
import { SUMMARIES_QUERY_KEY } from "@/hooks/useTickerSummaries";

export type RunAllStatus =
  | "idle"
  | "queued"
  | "running"
  | "completed"
  | "failed";

export type RunAllProgressEntry = {
  ticker: string;
  status: RunAllStatus;
  error?: string;
};

export type RunAllSnapshot = {
  isRunning: boolean;
  total: number;
  finished: number;
  failed: number;
  entries: Record<string, RunAllProgressEntry>;
};

const EMPTY_SNAPSHOT: RunAllSnapshot = {
  isRunning: false,
  total: 0,
  finished: 0,
  failed: 0,
  entries: {},
};

// The DIL pipeline + deliberation poll loops both run inside the single
// uvicorn worker's event loop. Two concurrent /research calls saturate it
// and cause new HTTP requests to be dropped at TCP level (which Chrome
// surfaces as a misleading "blocked by CORS policy" message). Sequential
// runs keep the loop responsive and let cards upgrade IDLE → RUNNING →
// COMPLETED visibly one at a time.
const DEFAULT_CONCURRENCY = 1;
const DEFAULT_DAYS = 7;

type UseRunAllOptions = {
  concurrency?: number;
  days?: number;
};

/**
 * Returns a snapshot + start/cancel handlers. The hook is intentionally
 * not a TanStack mutation because it manages a queue of N requests; the
 * underlying single-ticker call still goes through the same /research/:t
 * endpoint as `useRunAnalysis`.
 */
export function useRunAll(options: UseRunAllOptions = {}) {
  const concurrency = Math.max(1, options.concurrency ?? DEFAULT_CONCURRENCY);
  const days = options.days ?? DEFAULT_DAYS;
  const qc = useQueryClient();
  const cancelRef = useRef(false);
  const [snapshot, setSnapshot] = useState<RunAllSnapshot>(EMPTY_SNAPSHOT);

  const updateEntry = useCallback(
    (ticker: string, patch: Partial<RunAllProgressEntry>) => {
      setSnapshot((prev) => {
        const cur = prev.entries[ticker] ?? { ticker, status: "queued" };
        const next: RunAllProgressEntry = { ...cur, ...patch };
        const entries = { ...prev.entries, [ticker]: next };
        const finished = Object.values(entries).filter(
          (e) => e.status === "completed" || e.status === "failed",
        ).length;
        const failed = Object.values(entries).filter((e) => e.status === "failed").length;
        return { ...prev, entries, finished, failed };
      });
    },
    [],
  );

  const cancel = useCallback(() => {
    cancelRef.current = true;
  }, []);

  const start = useCallback(
    async (tickers: string[] = [...ALL_WATCHLIST_TICKERS]) => {
      cancelRef.current = false;
      setSnapshot({
        isRunning: true,
        total: tickers.length,
        finished: 0,
        failed: 0,
        entries: Object.fromEntries(
          tickers.map((t) => [t, { ticker: t, status: "queued" } as RunAllProgressEntry]),
        ),
      });

      const queue = [...tickers];

      const runOne = async (ticker: string): Promise<void> => {
        if (cancelRef.current) {
          updateEntry(ticker, { status: "failed", error: "cancelled" });
          return;
        }
        updateEntry(ticker, { status: "running" });
        try {
          // /research is the heaviest call in the system (full DIL pipeline).
          // Give it a wider timeout than the global axios default so a slow
          // backend doesn't surface as a misleading "Network Error".
          const { data } = await apiClient.get(`/research/${encodeURIComponent(ticker)}`, {
            params: { days },
            timeout: 240_000,
          });
          const report = researchReportSchema.parse(data) as ResearchReport;
          qc.setQueryData(["lastReport", ticker], report);

          // Splice fresh row in so the card paints immediately.
          const key = SUMMARIES_QUERY_KEY(ALL_WATCHLIST_TICKERS);
          qc.setQueryData<TickerSummaryRow[] | undefined>(key, (prev) => {
            if (!prev) return prev;
            const fallback = report.executive_summary ?? extractDashboardSummary(report);
            const reportId = report._pipeline_meta?.report_id ?? null;
            const snap = report._pipeline_meta?.price_snapshot;
            const status = (report as { deliberation_layer?: { status?: TickerSummaryRow["deliberation_status"] } }).deliberation_layer
              ?.status ?? null;
            return prev.map((row) =>
              row.ticker === ticker
                ? {
                    ...row,
                    report_id: reportId,
                    deliberation_status: status,
                    last_close: snap?.last_close ?? row.last_close,
                    session_change_pct: snap?.last_session_change_pct ?? row.session_change_pct,
                    executive_summary: fallback ?? row.executive_summary,
                    last_run_at: new Date().toISOString(),
                  }
                : row,
            );
          });

          updateEntry(ticker, { status: "completed" });
        } catch (err) {
          const message = err instanceof Error ? err.message : "Unknown error";
          updateEntry(ticker, { status: "failed", error: message });
        }
      };

      const workers: Promise<void>[] = [];
      for (let i = 0; i < concurrency; i++) {
        workers.push(
          (async () => {
            while (queue.length > 0) {
              if (cancelRef.current) {
                while (queue.length > 0) {
                  const t = queue.shift()!;
                  updateEntry(t, { status: "failed", error: "cancelled" });
                }
                return;
              }
              const ticker = queue.shift()!;
              await runOne(ticker);
            }
          })(),
        );
      }
      await Promise.all(workers);

      setSnapshot((prev) => ({ ...prev, isRunning: false }));
      qc.invalidateQueries({ queryKey: SUMMARIES_QUERY_KEY(ALL_WATCHLIST_TICKERS) });
    },
    [concurrency, days, qc, updateEntry],
  );

  return { snapshot, start, cancel };
}
