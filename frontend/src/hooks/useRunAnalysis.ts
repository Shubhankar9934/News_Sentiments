/**
 * Per-card "Run Analysis" mutation.
 *
 * Wraps the existing GET /research/{ticker} endpoint so each card carries
 * its own pending / error state without leaking across the grid. The DIL
 * pipeline behaviour is unchanged — this is exactly the same call the
 * legacy single-ticker workbench fires.
 *
 * On success the matching summary in the React-Query cache is updated
 * optimistically, then the `summaries` list is invalidated so the
 * 30s-refetch loop also picks up the new row.
 */

import {
  useMutation,
  useQueryClient,
  type UseMutationResult,
} from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { ALL_WATCHLIST_TICKERS } from "@/config/watchlist";
import { extractDashboardSummary } from "@/lib/extractDashboardSummary";
import {
  researchReportSchema,
  type ResearchReport,
  type TickerSummaryRow,
} from "@/types/schemas";
import { SUMMARIES_QUERY_KEY } from "@/hooks/useTickerSummaries";

const DEFAULT_DAYS = 7;

export function useRunAnalysis(
  ticker: string,
  days: number = DEFAULT_DAYS,
): UseMutationResult<ResearchReport, unknown, void> {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: ["run-analysis", ticker, days],
    mutationFn: async (): Promise<ResearchReport> => {
      const { data } = await apiClient.get(`/research/${encodeURIComponent(ticker)}`, {
        params: { days },
      });
      return researchReportSchema.parse(data);
    },
    onSuccess: (report) => {
      qc.setQueryData(["lastReport", ticker], report);

      // Splice the freshly-computed v1 summary into the existing grid cache
      // so the card paints immediately, ahead of the next refetch.
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

      // Trigger a refetch so the projection backed by Postgres also wins.
      qc.invalidateQueries({ queryKey: SUMMARIES_QUERY_KEY(ALL_WATCHLIST_TICKERS) });
    },
  });
}
