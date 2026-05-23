import { Card } from "@/components/ui/card";
import type { DeliberationLayer } from "@/types/schemas";
import { MODEL_LABELS, Pill, SectionTitle } from "./shared";

type Props = { layer: DeliberationLayer };

function pct(x: number | undefined): string {
  if (typeof x !== "number" || Number.isNaN(x)) return "—";
  return `${Math.round(x * 100)}%`;
}

export function CalibrationDisplay({ layer }: Props) {
  const c = layer.consensus;
  if (!c) return null;
  const cal = c.calibration;
  const support = c.support_counts ?? {};
  const total = Object.values(support).reduce(
    (sum, models) => sum + (Array.isArray(models) ? models.length : 0),
    0,
  );
  const supportEntries = Object.entries(support).filter(
    ([, models]) => Array.isArray(models) && models.length > 0,
  );

  if (!cal && supportEntries.length === 0 && !c.reconciled_label) {
    return null;
  }

  return (
    <Card className="p-4">
      <SectionTitle title="Calibration" />
      {cal && (
        <div className="mb-3 grid grid-cols-2 gap-2 md:grid-cols-4">
          <Metric label="Directional conviction" value={pct(cal.directional_conviction)} />
          <Metric label="Consensus strength" value={pct(cal.consensus_strength)} />
          <Metric label="Evidence quality" value={pct(cal.evidence_quality)} />
          <Metric label="Confidence (aggregate)" value={pct(cal.confidence_aggregate)} />
        </div>
      )}

      {c.reconciled_label && (
        <p className="mb-2 text-xs text-slate-600 dark:text-slate-400">
          <span className="font-semibold">Reconciled verdict: </span>
          <code className="rounded bg-[hsl(var(--muted))] px-1 py-0.5 text-[11px]">
            {c.reconciled_label}
          </code>
          <span className="ml-2 text-slate-500">(mean-score label: {c.consensus})</span>
        </p>
      )}

      {supportEntries.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="font-semibold text-slate-600 dark:text-slate-300">Support:</span>
          {supportEntries
            .sort(([, a], [, b]) => (b as string[]).length - (a as string[]).length)
            .map(([stance, models]) => {
              const list = models as string[];
              const labels = list.map((m) => MODEL_LABELS[m] ?? m).join(", ");
              return (
                <Pill key={stance}>
                  {stance} {list.length}/{total} ({labels})
                </Pill>
              );
            })}
        </div>
      )}

      <p className="mt-3 text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">
        Confidence aggregate is the mean of individual model confidences,
        dampened by model divergence — it can never exceed the average. Agreement
        score reflects directional spread; consensus strength reflects label
        unanimity. The two are reported separately to avoid conflating
        disagreement with confidence.
      </p>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-[hsl(var(--border))] bg-[hsl(var(--muted))]/30 p-2">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
        {label}
      </div>
      <div className="mt-1 text-lg font-bold text-slate-800 dark:text-slate-100">{value}</div>
    </div>
  );
}
