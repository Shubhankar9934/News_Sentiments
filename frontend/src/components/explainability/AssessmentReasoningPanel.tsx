import type { Explainability } from "@/types/schemas";
import { ExplainCard } from "./shared";

type Reasoning = NonNullable<Explainability["assessment_reasoning"]>;

const LENS_LABELS: Record<string, string> = {
  ticker_risk: "Ticker Risk",
  structure_risk: "Structure Risk",
  position_risk: "Position Risk",
  historical_analogs: "Historical Analogs",
  macro_transmission: "Macro Transmission",
};

export function AssessmentReasoningPanel({ data }: { data: Reasoning }) {
  if (!data.lenses || data.lenses.length === 0) return null;
  return (
    <ExplainCard
      title="Assessment Reasoning"
      subtitle={
        data.members_used.length
          ? `Synthesised across ${data.members_used.length} Assessment Team analysts`
          : "5-lens consensus across the Assessment Team"
      }
    >
      <div className="flex flex-col gap-3">
        {data.lenses.map((lens) => (
          <div
            key={lens.lens}
            className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--muted))] p-3"
          >
            <div className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
              {LENS_LABELS[lens.lens] ?? lens.lens}
            </div>
            <p className="mt-1 text-sm text-slate-700 dark:text-slate-200">
              {lens.summary}
            </p>
            {lens.member_views.length > 0 && (
              <ul className="mt-2 ml-4 list-disc text-xs text-slate-500 dark:text-slate-400">
                {lens.member_views.slice(0, 3).map((view, idx) => (
                  <li key={idx}>{view}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </ExplainCard>
  );
}
