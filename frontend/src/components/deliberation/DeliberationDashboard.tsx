import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDeliberation } from "@/hooks/useDeliberation";
import { getPipelineMeta } from "@/lib/pipelineMeta";
import type { DeliberationLayer, ResearchReport } from "@/types/schemas";
import { CalibrationDisplay } from "./CalibrationDisplay";
import { ConsensusPanel } from "./ConsensusPanel";
import { ConfidenceDriftChart } from "./ConfidenceDriftChart";
import { ContradictionAnalysisPanel } from "./ContradictionAnalysisPanel";
import { ConvictionHeatmap } from "./ConvictionHeatmap";
import { DebateTimeline } from "./DebateTimeline";
import { DisagreementMatrix } from "./DisagreementMatrix";
import { DisagreementTopology } from "./DisagreementTopology";
import { HiddenRisksPanel } from "./HiddenRisksPanel";
import { InstitutionalVerdict } from "./InstitutionalVerdict";
import { ModelOpinionCards } from "./ModelOpinionCards";
import { ReasoningTree } from "./ReasoningTree";
import { CouncilPanel } from "./CouncilPanel";
import { ResearchDesksPanel } from "./ResearchDesksPanel";
import { ThesisClusterSummary } from "./ThesisClusterSummary";
import { Pill } from "./shared";

type Props = {
  ticker: string;
  report: ResearchReport;
  isDark: boolean;
};

function parseInitialLayer(report: ResearchReport): DeliberationLayer | undefined {
  const raw = (report as ResearchReport & { deliberation_layer?: unknown }).deliberation_layer;
  if (!raw || typeof raw !== "object") return undefined;
  return raw as DeliberationLayer;
}

export function DeliberationDashboard({ report, isDark }: Props) {
  const meta = getPipelineMeta(report);
  const reportId = meta?.report_id as string | undefined;
  const initial = parseInitialLayer(report);
  const { data: layer, isLoading, isError } = useDeliberation(reportId, initial);

  const status = layer?.status;
  const unavailable = !reportId && !initial;
  const skipped = status === "skipped";
  const failed = status === "failed";
  const pending = status === "pending" || status === "running";

  return (
    <section className="mt-6 space-y-4" aria-label="AI Deliberation and Institutional Consensus">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-bold uppercase tracking-[0.12em] text-slate-600 dark:text-slate-300">
          AI Deliberation &amp; Institutional Consensus
        </h2>
        {status && <Pill tone={pending ? "warn" : failed ? "bad" : "neutral"}>{status}</Pill>}
      </div>

      {unavailable && (
        <Card className="p-4">
          <p className="text-sm text-slate-500">
            Deliberation not available for this run (legacy report or not persisted).
          </p>
        </Card>
      )}

      {!unavailable && (isLoading || pending) && !layer?.round1 && (
        <Card className="p-4 space-y-2">
          <p className="text-sm text-slate-600 dark:text-slate-300">
            {status === "running"
              ? "Deliberation running — querying GPT, Claude, and DeepSeek (this can take 2–5 minutes)…"
              : "Multi-model deliberation in progress…"}
          </p>
          {layer?.desks_requested && layer.desks_requested.length > 0 && (
            <p className="text-xs text-slate-500">
              Desks: {layer.desks_requested.map((d) => d.replace(/_desk$/, "")).join(", ")}
            </p>
          )}
          {layer?.models_requested && layer.models_requested.length > 0 && !layer.desks_requested?.length && (
            <p className="text-xs text-slate-500">
              Models: {layer.models_requested.join(", ")}
            </p>
          )}
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-24 w-full" />
        </Card>
      )}

      {skipped && (
        <Card className="p-4">
          <p className="text-sm text-slate-500">
            Deliberation skipped: {layer?.skip_reason ?? "insufficient models configured"}
          </p>
        </Card>
      )}

      {failed && (
        <Card className="p-4">
          <p className="text-sm text-rose-600">{layer?.error ?? "Deliberation failed"}</p>
        </Card>
      )}

      {isError && (
        <Card className="p-4">
          <p className="text-sm text-rose-600">Could not load deliberation status.</p>
        </Card>
      )}

      {layer && status === "complete" && (
        <div className="space-y-4">
          <ResearchDesksPanel layer={layer} />
          <CouncilPanel layer={layer} />
          <ThesisClusterSummary layer={layer} />
          <ModelOpinionCards layer={layer} />
          <ReasoningTree layer={layer} />
          <DebateTimeline layer={layer} />
          <ContradictionAnalysisPanel layer={layer} />
          <DisagreementMatrix layer={layer} />
          <ConvictionHeatmap layer={layer} />
          <DisagreementTopology layer={layer} />
          <ConfidenceDriftChart layer={layer} isDark={isDark} />
          <HiddenRisksPanel layer={layer} />
          <ConsensusPanel layer={layer} />
          <CalibrationDisplay layer={layer} />
          <InstitutionalVerdict layer={layer} />
        </div>
      )}
    </section>
  );
}
