import type { Explainability } from "@/types/schemas";
import { ExplainCard, ExplainRow, gradeTone } from "./shared";

type Calibration = NonNullable<Explainability["confidence_calibration"]>;

function pctOrDash(value: number | null | undefined) {
  if (value === null || value === undefined) return null;
  return `${value.toFixed(1)}%`;
}

export function ConfidenceCalibrationPanel({ data }: { data: Calibration }) {
  return (
    <ExplainCard
      title="Confidence Calibration"
      subtitle={`Why Confidence = ${data.final_confidence_bucket} (${data.final_confidence_pct.toFixed(1)}%)`}
    >
      <ExplainRow
        label={data.raw_desk_confidence.label}
        detail={data.raw_desk_confidence.explanation}
        value={pctOrDash(data.raw_desk_confidence.value ?? null)}
      />
      <ExplainRow
        label={data.cross_agent_agreement.label}
        detail={data.cross_agent_agreement.explanation}
        value={pctOrDash(data.cross_agent_agreement.value ?? null)}
      />
      <ExplainRow
        label={data.evidence_overlap.label}
        detail={data.evidence_overlap.explanation}
        value={pctOrDash(data.evidence_overlap.value ?? null)}
      />
      <ExplainRow
        label={data.contradiction_penalty.label}
        detail={data.contradiction_penalty.explanation}
        value={pctOrDash(data.contradiction_penalty.value ?? null)}
        tone="bad"
      />
      {data.council_confidence && (
        <ExplainRow
          label={data.council_confidence.label}
          detail={data.council_confidence.explanation}
          value={pctOrDash(data.council_confidence.value ?? null)}
        />
      )}
      <div className="flex items-center justify-between border-t border-[hsl(var(--border))] pt-2">
        <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">
          Final Confidence
        </span>
        <span
          className={`rounded-full border px-2.5 py-0.5 text-sm font-semibold ${
            gradeTone(data.final_confidence_bucket) === "ok"
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200"
              : gradeTone(data.final_confidence_bucket) === "warn"
                ? "border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-100"
                : "border-rose-500/30 bg-rose-500/10 text-rose-800 dark:text-rose-200"
          }`}
        >
          {data.final_confidence_bucket} · {data.final_confidence_pct.toFixed(1)}%
        </span>
      </div>
    </ExplainCard>
  );
}
