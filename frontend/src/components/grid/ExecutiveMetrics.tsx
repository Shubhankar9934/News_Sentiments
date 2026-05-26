import { MetricCell, SectionFrame } from "@/components/grid/primitives";
import {
  outlookTone,
  toneFor,
  toneForScore,
} from "@/lib/deriveDecisionTone";
import type { ExecutiveSummary } from "@/types/schemas";

type Props = {
  summary: ExecutiveSummary | null;
};

export function ExecutiveMetrics({ summary }: Props) {
  return (
    <SectionFrame title="Executive Metrics">
      <div className="grid grid-cols-2 gap-2">
        <MetricCell
          label="Credit Safety"
          emphasis
          tone={summary ? toneForScore(summary.credit_safety_score) : "neutral"}
          value={
            summary ? (
              <>
                {summary.credit_safety_score.toFixed(1)}
                <span className="text-xs font-normal text-slate-500">/10</span>
              </>
            ) : (
              "—"
            )
          }
        />
        <MetricCell
          label="Outlook"
          emphasis
          tone={summary ? outlookTone(summary.outlook) : "neutral"}
          value={summary?.outlook ?? "—"}
        />
        <MetricCell
          label="Risk"
          emphasis
          tone={summary ? toneFor(summary.risk) : "neutral"}
          value={summary?.risk ?? "—"}
        />
        <MetricCell
          label="Confidence"
          emphasis
          tone={summary ? toneFor(summary.confidence) : "neutral"}
          value={summary?.confidence ?? "—"}
        />
      </div>
    </SectionFrame>
  );
}
