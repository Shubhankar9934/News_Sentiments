import { Card } from "@/components/ui/card";
import type { DeliberationLayer } from "@/types/schemas";
import { Pill, SectionTitle } from "./shared";

type Props = { layer: DeliberationLayer };

type TopologyAxes = {
  directional?: number;
  confidence?: number;
  evidence?: number;
  risk?: number;
  timing?: number;
};

type Topology = {
  axes?: TopologyAxes;
  overall?: number;
  hot_topics?: string[];
};

const AXIS_LABELS: Record<keyof TopologyAxes, string> = {
  directional: "Directional",
  confidence: "Confidence",
  evidence: "Evidence",
  risk: "Risk",
  timing: "Timing",
};

const AXIS_ORDER: (keyof TopologyAxes)[] = [
  "directional",
  "confidence",
  "evidence",
  "risk",
  "timing",
];

export function DisagreementTopology({ layer }: Props) {
  const topology =
    (layer.metrics as { disagreement_topology?: Topology } | undefined)
      ?.disagreement_topology ?? null;
  if (!topology || !topology.axes) return null;

  const axes = topology.axes;
  const hot = topology.hot_topics ?? [];
  const overall = topology.overall ?? 0;

  return (
    <Card className="p-4">
      <SectionTitle title="Disagreement topology">
        <Pill tone={overall > 0.6 ? "bad" : overall > 0.3 ? "warn" : "ok"}>
          overall {Math.round(overall * 100)}%
        </Pill>
      </SectionTitle>
      <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">
        Where the panel refuses to converge — disagreement is treated as signal,
        not noise. Each axis is normalized to [0, 1]; higher means more divergence.
      </p>
      <div className="space-y-2">
        {AXIS_ORDER.map((key) => {
          const v = axes[key] ?? 0;
          const pct = Math.round(v * 100);
          const tone = v > 0.6 ? "bg-rose-500" : v > 0.3 ? "bg-amber-500" : "bg-emerald-500";
          return (
            <div key={key} className="grid grid-cols-[120px_1fr_48px] items-center gap-2">
              <span className="text-xs font-medium text-slate-700 dark:text-slate-200">
                {AXIS_LABELS[key]}
              </span>
              <div className="relative h-3 overflow-hidden rounded bg-[hsl(var(--muted))]">
                <div
                  className={`absolute inset-y-0 left-0 ${tone}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="text-right text-xs tabular-nums text-slate-600 dark:text-slate-300">
                {pct}%
              </span>
            </div>
          );
        })}
      </div>

      {hot.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <span className="font-semibold text-slate-600 dark:text-slate-300">Hot topics:</span>
          {hot.map((t) => (
            <Pill key={t} tone="bad">
              {t}
            </Pill>
          ))}
        </div>
      )}
    </Card>
  );
}
