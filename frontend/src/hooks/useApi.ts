import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { healthSchema, researchReportSchema, type Health, type ResearchReport } from "@/types/schemas";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: async (): Promise<Health> => {
      const { data } = await apiClient.get("/health");
      return healthSchema.parse(data);
    },
    staleTime: 15_000,
  });
}

export function useResearch(ticker: string, days: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: ["research", ticker, days],
    mutationFn: async (): Promise<ResearchReport> => {
      const { data } = await apiClient.get(`/research/${encodeURIComponent(ticker)}`, {
        params: { days },
      });
      const parsed = researchReportSchema.parse(data);
      return parsed;
    },
    onSuccess: (report) => {
      qc.setQueryData(["lastReport", ticker], report);
    },
  });
}

export function useHistory(ticker: string, enabled: boolean) {
  return useQuery({
    queryKey: ["history", ticker],
    queryFn: async () => {
      const { data } = await apiClient.get(`/history/${encodeURIComponent(ticker)}`, {
        params: { limit: 10 },
      });
      return data as Array<{
        id: string;
        time_window: string | null;
        data_mode: string | null;
        articles_ct: number | null;
        created_at: string;
        report_json: ResearchReport;
      }>;
    },
    enabled: enabled && ticker.length > 0,
  });
}

export function useAnalogs(ticker: string, eventType: string, enabled: boolean) {
  return useQuery({
    queryKey: ["analogs", ticker, eventType],
    queryFn: async () => {
      const { data } = await apiClient.get(
        `/analogs/${encodeURIComponent(ticker)}/${encodeURIComponent(eventType)}`
      );
      return data as unknown[];
    },
    enabled: enabled && ticker.length > 0 && eventType.length > 0,
  });
}
