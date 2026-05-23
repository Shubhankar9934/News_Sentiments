import { Suspense, useMemo, useState } from "react";
import { Loader2, Moon, Sun } from "lucide-react";
import { toast } from "sonner";
import { DeliberationDashboard } from "@/components/deliberation/DeliberationDashboard";
import { TradingIntelligenceDashboard, type AnalogRow } from "@/components/trading/TradingIntelligenceDashboard";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAnalogs, useHealth, useHistory, useResearch } from "@/hooks/useApi";
import { useResearchProgress } from "@/hooks/useResearchProgress";
import { useThemeStore } from "@/store/theme";
import { pickDominantEventType } from "@/lib/pipelineMeta";
import type { ResearchReport } from "@/types/schemas";

function HealthStrip() {
  const { data, isLoading, refetch, isFetching } = useHealth();
  if (isLoading) return <Skeleton className="h-10 w-full" />;
  const ok = !!data;
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--muted))] px-3 py-2 text-sm">
      <div>
        <span className="font-medium">{ok ? "Backend online" : "Backend unreachable"}</span>
        {data && (
          <span className="ml-2 text-xs text-slate-600 dark:text-slate-300">
            v{data.version} · db {data.db ? "✓" : "✗"} · redis {data.redis ? "✓" : "✗"} · qdrant{" "}
            {data.qdrant ? "✓" : "✗"}
          </span>
        )}
      </div>
      <Button variant="outline" size="sm" onClick={() => void refetch()} disabled={isFetching}>
        {isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : "Retry"}
      </Button>
    </div>
  );
}

export function DashboardPage() {
  const [ticker, setTicker] = useState("NVDA");
  const [days, setDays] = useState(7);
  const [report, setReport] = useState<ResearchReport | null>(null);
  const theme = useThemeStore((s) => s.theme);
  const toggleTheme = useThemeStore((s) => s.toggle);
  const research = useResearch(ticker, days);
  const history = useHistory(ticker, true);
  const ws = useResearchProgress();

  const wsPreview = useMemo(() => ws.messages.slice(-6), [ws.messages]);

  const dominantEvent = report ? pickDominantEventType(report) : null;
  const analogQuery = useAnalogs(ticker, dominantEvent ?? "Earnings", Boolean(report));

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Trading intelligence desk</h1>
          <p className="text-sm text-slate-600 dark:text-slate-300">
            Should you consider trading this name today? News → context → conviction — with source links you can
            verify.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={toggleTheme} aria-label="Toggle theme">
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
      </div>

      <Suspense fallback={<Skeleton className="h-10 w-full" />}>
        <HealthStrip />
      </Suspense>

      <Card className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label className="text-xs font-medium text-slate-600 dark:text-slate-300">Ticker</label>
          <input
            className="mt-1 w-full rounded-md border border-[hsl(var(--border))] bg-transparent px-3 py-2 font-mono text-sm"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
          />
        </div>
        <div className="w-40">
          <label className="text-xs font-medium text-slate-600 dark:text-slate-300">Days</label>
          <input
            type="number"
            min={1}
            max={90}
            className="mt-1 w-full rounded-md border border-[hsl(var(--border))] bg-transparent px-3 py-2 text-sm"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          />
        </div>
        <div className="flex gap-2">
          <Button
            disabled={research.isPending || !ticker}
            onClick={async () => {
              try {
                const r = await research.mutateAsync();
                setReport(r);
                toast.success("Research complete");
              } catch {
                toast.error("Research failed");
              }
            }}
          >
            {research.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> Running…
              </>
            ) : (
              "Run (HTTP)"
            )}
          </Button>
          <Button
            variant="outline"
            disabled={!ticker}
            onClick={() => {
              ws.run(ticker, days);
              toast.message("WebSocket run started — watch progress below");
            }}
          >
            Run (WS)
          </Button>
        </div>
      </Card>

      {wsPreview.length > 0 && (
        <Card>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
            Live progress
          </div>
          <ul className="mt-2 space-y-1 text-sm">
            {wsPreview.map((m, idx) => (
              <li key={`${m.stage}-${idx}`}>
                <span className="font-mono text-xs text-slate-500">{m.stage}</span> · {m.message}
              </li>
            ))}
          </ul>
          {ws.lastError && <p className="mt-2 text-sm text-red-600">WS: {ws.lastError}</p>}
        </Card>
      )}

      {history.data && history.data.length > 0 && (
        <Card>
          <div className="text-sm font-semibold">Recent reports</div>
          <div className="mt-2 space-y-2">
            {history.data.slice(0, 5).map((h) => (
              <button
                key={h.id}
                type="button"
                className="flex w-full items-center justify-between rounded-md border border-[hsl(var(--border))] px-3 py-2 text-left text-sm hover:bg-[hsl(var(--muted))]"
                onClick={() => setReport(h.report_json)}
              >
                <span>
                  {h.time_window} · {h.articles_ct ?? 0} articles
                </span>
                <span className="text-xs text-slate-500">{new Date(h.created_at).toLocaleString()}</span>
              </button>
            ))}
          </div>
        </Card>
      )}

      {report && (
        <>
          <TradingIntelligenceDashboard
            ticker={ticker}
            report={report}
            isDark={theme === "dark"}
            analogRows={(analogQuery.data as AnalogRow[] | undefined) ?? []}
            analogsLoading={analogQuery.isLoading}
            dominantEventLabel={dominantEvent}
          />
          <DeliberationDashboard ticker={ticker} report={report} isDark={theme === "dark"} />
        </>
      )}
    </div>
  );
}
