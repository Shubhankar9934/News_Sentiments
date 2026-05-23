import { Card } from "@/components/ui/card";
import type { DeliberationLayer } from "@/types/schemas";
import { MODEL_LABELS, Pill, SectionTitle, stanceTone } from "./shared";

type Props = { layer: DeliberationLayer };

type Cell = { stance: string; confidence: number; risk_score: number };
type Heatmap = {
  topics?: string[];
  models?: string[];
  cells?: Record<string, Record<string, Cell>>;
};

function riskShade(score: number): string {
  if (score >= 0.66) return "bg-rose-500/30";
  if (score >= 0.33) return "bg-amber-500/20";
  if (score > 0) return "bg-emerald-500/10";
  return "";
}

export function ConvictionHeatmap({ layer }: Props) {
  const heatmap =
    (layer.metrics as { conviction_heatmap?: Heatmap } | undefined)?.conviction_heatmap ?? null;
  if (!heatmap || !heatmap.topics?.length || !heatmap.models?.length || !heatmap.cells) {
    return null;
  }
  const { topics, models, cells } = heatmap as Required<Heatmap>;

  return (
    <Card className="p-4">
      <SectionTitle title="Conviction heatmap" />
      <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">
        Topic × model. Pill tone shows directional stance, percentage is model
        confidence, background shade is the risk weight that model surfaced
        on that topic.
      </p>
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse text-xs">
          <thead>
            <tr>
              <th className="border-b border-[hsl(var(--border))] p-2 text-left font-semibold">
                Topic
              </th>
              {models.map((m) => (
                <th
                  key={m}
                  className="border-b border-[hsl(var(--border))] p-2 text-left font-semibold"
                >
                  {MODEL_LABELS[m] ?? m}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {topics.map((topic) => (
              <tr key={topic} className="border-b border-[hsl(var(--border))]">
                <td className="p-2 font-medium text-slate-700 dark:text-slate-200">{topic}</td>
                {models.map((m) => {
                  const cell = cells[topic]?.[m];
                  if (!cell) {
                    return (
                      <td key={m} className="p-2 text-slate-400">
                        —
                      </td>
                    );
                  }
                  return (
                    <td key={m} className={`p-2 ${riskShade(cell.risk_score)}`}>
                      <div className="flex flex-col gap-1">
                        <Pill tone={stanceTone(cell.stance)}>{cell.stance}</Pill>
                        <span className="text-[10px] text-slate-600 dark:text-slate-300">
                          conf {Math.round(cell.confidence * 100)}%
                          {cell.risk_score > 0
                            ? ` · risk ${Math.round(cell.risk_score * 100)}%`
                            : ""}
                        </span>
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
