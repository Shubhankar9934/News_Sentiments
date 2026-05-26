import { Card } from "@/components/ui/card";
import type { DeliberationLayer } from "@/types/schemas";
import { deskLabel, modelTooltip, SectionTitle } from "./shared";

type Props = { layer: DeliberationLayer; isDark: boolean };

export function ConfidenceDriftChart({ layer }: Props) {
  const drift = layer.metrics?.confidence_drift ?? [];
  const maxVal = 1;

  return (
    <Card className="p-4">
      <SectionTitle title="Confidence drift" />
      <div className="space-y-4">
        {drift.map((d) => (
          <div key={d.model}>
            <div className="mb-1 flex justify-between text-xs">
              <span className="font-semibold" title={modelTooltip(d.model)}>{deskLabel(d.model)}</span>
              <span className="text-slate-500">
                {Math.round(d.before * 100)}% → {Math.round(d.after * 100)}% (
                {d.delta >= 0 ? "+" : ""}
                {Math.round(d.delta * 100)}%)
              </span>
            </div>
            <div className="relative h-6 rounded bg-[hsl(var(--muted))]">
              <div
                className="absolute top-1 h-4 rounded bg-slate-400/60"
                style={{
                  left: `${(d.before / maxVal) * 100}%`,
                  width: `${Math.max(2, ((d.after - d.before) / maxVal) * 100)}%`,
                  transform: d.after < d.before ? "translateX(-100%)" : undefined,
                }}
              />
              <div
                className="absolute top-1 h-4 w-1 rounded bg-indigo-500"
                style={{ left: `${(d.before / maxVal) * 100}%` }}
                title="Before debate"
              />
              <div
                className="absolute top-1 h-4 w-1 rounded bg-emerald-500"
                style={{ left: `${(d.after / maxVal) * 100}%` }}
                title="After debate"
              />
            </div>
          </div>
        ))}
        {drift.length === 0 && (
          <p className="text-sm text-slate-500">No confidence revisions recorded.</p>
        )}
      </div>
    </Card>
  );
}
