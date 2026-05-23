import { Card } from "@/components/ui/card";
import type { DeliberationLayer, StructuredRisk } from "@/types/schemas";
import { MODEL_LABELS, Pill, SectionTitle } from "./shared";

type Props = { layer: DeliberationLayer };

function severityTone(s: string | undefined): "ok" | "warn" | "bad" | "neutral" {
  if (s === "high") return "bad";
  if (s === "medium") return "warn";
  if (s === "low") return "ok";
  return "neutral";
}

function StructuredRiskList({
  risks,
  totalModels,
}: {
  risks: StructuredRisk[];
  totalModels: number;
}) {
  return (
    <ul className="space-y-3">
      {risks.map((r) => {
        const supportLabels = (r.support_models ?? [])
          .map((m) => MODEL_LABELS[m] ?? m)
          .join(", ");
        const fraction =
          totalModels > 0 ? `${r.support_count ?? 0}/${totalModels}` : `${r.support_count ?? 0}`;
        return (
          <li
            key={r.cluster_id}
            className="rounded border border-[hsl(var(--border))] p-3 text-sm"
          >
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <span className="font-semibold">{r.headline}</span>
              <Pill tone={severityTone(r.severity)}>{r.severity ?? "—"}</Pill>
              <Pill>
                {fraction} models{supportLabels ? ` (${supportLabels})` : ""}
              </Pill>
              {r.topic && r.topic !== "other" && <Pill>{r.topic}</Pill>}
            </div>
            {r.members && r.members.length > 1 && (
              <details className="text-xs text-slate-600 dark:text-slate-400">
                <summary className="cursor-pointer">
                  {r.members.length} phrasings across models
                </summary>
                <ul className="mt-1 list-inside list-disc space-y-0.5 pl-1">
                  {r.members.map((m, i) => (
                    <li key={i}>{m}</li>
                  ))}
                </ul>
              </details>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function LegacyRiskList({ items }: { items: string[] }) {
  // Same exact-string dedup the panel used historically, preserved for
  // reports created before PR4.
  const seen = new Set<string>();
  const out: string[] = [];
  for (const r of items) {
    const k = r.trim().toLowerCase();
    if (k && !seen.has(k)) {
      seen.add(k);
      out.push(r);
    }
  }
  return (
    <ul className="list-inside list-disc space-y-1 text-sm text-slate-700 dark:text-slate-300">
      {out.slice(0, 20).map((r, i) => (
        <li key={i}>{r}</li>
      ))}
    </ul>
  );
}

export function HiddenRisksPanel({ layer }: Props) {
  const structured = layer.consensus?.structured_risks ?? [];
  const totalModels = Object.keys(layer.round1 ?? {}).length;

  if (structured.length > 0) {
    return (
      <Card className="p-4">
        <SectionTitle title="Hidden risks">
          <span className="text-[11px] text-slate-500">
            {structured.length} cluster{structured.length === 1 ? "" : "s"} across {totalModels} models
          </span>
        </SectionTitle>
        <StructuredRiskList risks={structured} totalModels={totalModels} />
      </Card>
    );
  }

  // Legacy back-compat — old reports have no structured_risks.
  const fromConsensus = layer.consensus?.hidden_risks ?? [];
  const fromRound1 = Object.values(layer.round1 ?? {}).flatMap((op) => [
    ...(op.key_risks ?? []),
    ...(op.hidden_assumptions ?? []),
  ]);
  const fromDebate = (layer.debate_rounds ?? []).flatMap((rd) =>
    Object.values(rd).flatMap((c) => c.new_risks_identified ?? []),
  );
  const all = [...fromConsensus, ...fromDebate, ...fromRound1];

  return (
    <Card className="p-4">
      <SectionTitle title="Hidden risks" />
      {all.length === 0 ? (
        <p className="text-sm text-slate-500">No aggregated risks yet.</p>
      ) : (
        <LegacyRiskList items={all} />
      )}
    </Card>
  );
}
