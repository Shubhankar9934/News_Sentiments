/**
 * Mutations that kick the backend's sequential watchlist refresh.
 *
 * Two server-side endpoints, one mutation each:
 *   POST /api/v1/dashboard/refresh          - full 12-ticker batch
 *   POST /api/v1/dashboard/refresh/:ticker  - single ticker
 *
 * The backend owns sequencing now; the browser optimistically updates queue
 * state on click, then reconciles with the server response.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiClient } from "@/api/client";
import {
  DASHBOARD_CARDS_QUERY_KEY,
  dashboardTickerReportQueryKey,
  invalidateAllLatestReports,
  LATEST_REPORT_QUERY_KEY,
} from "@/hooks/useDashboardCards";
import {
  watchlistBatchStatusSchema,
  type DashboardTickersResponse,
  type WatchlistBatchStatus,
} from "@/types/schemas";

async function postRefreshAll(): Promise<WatchlistBatchStatus> {
  const { data } = await apiClient.post("/dashboard/refresh");
  return watchlistBatchStatusSchema.parse(data);
}

async function postRefreshTicker(ticker: string): Promise<WatchlistBatchStatus> {
  const { data } = await apiClient.post(
    `/dashboard/refresh/${encodeURIComponent(ticker)}`,
  );
  return watchlistBatchStatusSchema.parse(data);
}

function applyQueuedTicker(
  status: WatchlistBatchStatus,
  ticker: string,
): WatchlistBatchStatus {
  const upper = ticker.toUpperCase();
  if (status.current_ticker === upper || status.queued.includes(upper)) {
    return status;
  }

  const pipelineBusy =
    status.state === "running" &&
    (status.current_ticker != null || status.queued.length > 0);

  if (pipelineBusy) {
    return {
      ...status,
      state: "running",
      queued: [...status.queued, upper],
    };
  }

  return {
    ...status,
    state: "running",
    current_ticker: upper,
    queued: status.queued,
  };
}

export function useRefreshDashboard() {
  const qc = useQueryClient();

  const refreshAll = useMutation({
    mutationFn: postRefreshAll,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: DASHBOARD_CARDS_QUERY_KEY });
      invalidateAllLatestReports(qc);
      toast.success("Watchlist refresh queued");
    },
    onError: (err) => {
      const status = (err as { response?: { status?: number } }).response?.status;
      if (status === 409) {
        toast.info("A refresh is already running");
      } else {
        const message = err instanceof Error ? err.message : "Refresh failed";
        toast.error(`Could not start refresh: ${message}`);
      }
    },
  });

  const refreshTicker = useMutation({
    mutationFn: (ticker: string) => postRefreshTicker(ticker),
    onMutate: async (ticker) => {
      await qc.cancelQueries({ queryKey: DASHBOARD_CARDS_QUERY_KEY });
      qc.setQueryData<DashboardTickersResponse>(DASHBOARD_CARDS_QUERY_KEY, (old) => {
        if (!old) return old;
        return { ...old, status: applyQueuedTicker(old.status, ticker) };
      });
    },
    onSuccess: (data, ticker) => {
      qc.setQueryData<DashboardTickersResponse>(DASHBOARD_CARDS_QUERY_KEY, (old) =>
        old ? { ...old, status: data } : old,
      );
      void qc.invalidateQueries({ queryKey: DASHBOARD_CARDS_QUERY_KEY });
      void qc.invalidateQueries({ queryKey: [LATEST_REPORT_QUERY_KEY, ticker.toUpperCase()] });
      void qc.invalidateQueries({
        queryKey: dashboardTickerReportQueryKey(ticker.toUpperCase()),
      });
      const runningNow = data.current_ticker === ticker.toUpperCase();
      const queued = (data.queued ?? []).includes(ticker.toUpperCase());
      toast.success(
        runningNow
          ? `${ticker} analysis started`
          : queued
            ? `${ticker} queued for analysis`
            : `${ticker} refresh accepted`,
      );
    },
    onError: (err, _ticker, _ctx) => {
      qc.invalidateQueries({ queryKey: DASHBOARD_CARDS_QUERY_KEY });
      const message = err instanceof Error ? err.message : "Refresh failed";
      toast.error(`Refresh failed: ${message}`);
    },
  });

  return { refreshAll, refreshTicker };
}
