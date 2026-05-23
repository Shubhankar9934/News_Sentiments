import { Card } from "@/components/ui/card";
import type { DeliberationLayer, ThesisCluster } from "@/types/schemas";
import { MODEL_LABELS, Pill, SectionTitle, stanceTone } from "./shared";

type Props = { layer: DeliberationLayer };

function ThesisCard({
  cluster,
  totalModels,
}: {
  cluster: ThesisCluster;
  totalModels: number;
}) {
  const tone = stanceTone(cluster.stance);
  const models = cluster.models ?? [];
  return (
    <div className="rounded-md border border-[hsl(var(--border))] p-3">
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <Pill tone={tone}>{cluster.stance}</Pill>
        <Pill>
          {cluster.support_count ?? models.length}/{totalModels} models
        </Pill>
        {models.length > 0 && (
          <span className="text-xs text-slate-500">
            {models.map((m) => MODEL_LABELS[m] ?? m).join(", ")}
          </span>
        )}
      </div>
      {cluster.summary && (
        <p className="mb-2 text-xs font-medium text-slate-700 dark:text-slate-200">
          {cluster.summary}
        </p>
      )}
      {cluster.bullets && cluster.bullets.length > 0 ? (
        <ul className="list-inside list-disc space-y-1 text-xs text-slate-600 dark:text-slate-300">
          {cluster.bullets.map((b, i) => (
            <li key={i}>{b}</li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-slate-500">No reasoning headlines available.</p>
      )}
    </div>
  );
}

export function ThesisClusterSummary({ layer }: Props) {
  const clusters = layer.consensus?.thesis_clusters ?? [];
  if (clusters.length === 0) return null;
  const totalModels = Object.keys(layer.round1 ?? {}).length;

  return (
    <Card className="p-4">
      <SectionTitle title="Thesis clusters">
        <span className="text-[11px] text-slate-500">
          {clusters.length} narrative group{clusters.length === 1 ? "" : "s"}
        </span>
      </SectionTitle>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {clusters.map((c, idx) => (
          <ThesisCard key={`${c.stance}-${idx}`} cluster={c} totalModels={totalModels} />
        ))}
      </div>
    </Card>
  );
}
