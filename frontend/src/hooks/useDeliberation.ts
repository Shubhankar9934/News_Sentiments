import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { deliberationLayerSchema, type DeliberationLayer } from "@/types/schemas";

const POLL_MS = 5000;

export function useDeliberation(reportId: string | undefined, initial?: DeliberationLayer) {
  return useQuery({
    queryKey: ["deliberation", reportId],
    queryFn: async (): Promise<DeliberationLayer> => {
      const { data } = await apiClient.get(`/reports/${reportId}/deliberation`);
      return deliberationLayerSchema.parse(data);
    },
    enabled: Boolean(reportId),
    initialData: initial,
    refetchInterval: (query) => {
      const status = query.state.data?.status ?? initial?.status;
      return status === "pending" || status === "running" ? POLL_MS : false;
    },
    retry: (failureCount, error) => {
      const status = (error as { response?: { status?: number } }).response?.status;
      return status === 429 && failureCount < 5;
    },
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30_000),
  });
}
