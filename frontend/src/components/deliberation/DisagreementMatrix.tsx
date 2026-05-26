import { Card } from "@/components/ui/card";
import type { DeliberationLayer } from "@/types/schemas";
import { deskLabel, Pill, SectionTitle } from "./shared";

type Props = { layer: DeliberationLayer };

function alignTone(align: string | undefined): "ok" | "warn" | "bad" | "neutral" {
  if (align === "agree") return "ok";
  if (align === "oppose") return "bad";
  if (align === "split") return "warn";
  return "neutral";
}

export function DisagreementMatrix({ layer }: Props) {
  const matrix = layer.metrics?.disagreement_matrix ?? {};
  const topics = Object.keys(matrix).filter((t) => !t.startsWith("_"));

  const models = new Set<string>();
  for (const topic of topics) {
    const row = matrix[topic] ?? {};
    for (const k of Object.keys(row)) {
      if (!k.startsWith("_")) models.add(k);
    }
  }
  const modelList = Array.from(models);

  return (
    <Card className="p-4">
      <SectionTitle title="Disagreement matrix" />
      <p className="mb-3 text-xs text-slate-500">
        Divergence by topic — disagreement is signal, not noise.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[480px] border-collapse text-xs">
          <thead>
            <tr>
              <th className="border border-[hsl(var(--border))] bg-[hsl(var(--muted))] p-2 text-left">
                Topic
              </th>
              {modelList.map((m) => (
                <th
                  key={m}
                  className="border border-[hsl(var(--border))] bg-[hsl(var(--muted))] p-2 text-center"
                >
                  {deskLabel(m)}
                </th>
              ))}
              <th className="border border-[hsl(var(--border))] bg-[hsl(var(--muted))] p-2 text-center">
                Align
              </th>
            </tr>
          </thead>
          <tbody>
            {topics.map((topic) => {
              const row = matrix[topic] ?? {};
              const align = row._alignment as string | undefined;
              return (
                <tr key={topic}>
                  <td className="border border-[hsl(var(--border))] p-2 font-medium capitalize">
                    {topic}
                  </td>
                  {modelList.map((m) => (
                    <td
                      key={m}
                      className="border border-[hsl(var(--border))] p-2 text-center capitalize"
                    >
                      {row[m] ?? "—"}
                    </td>
                  ))}
                  <td className="border border-[hsl(var(--border))] p-2 text-center">
                    <Pill tone={alignTone(align)}>{align ?? "—"}</Pill>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
