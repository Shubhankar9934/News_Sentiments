import { Card } from "@/components/ui/card";
import type { DeliberationLayer } from "@/types/schemas";
import { Pill, SectionTitle, stanceTone } from "./shared";

type DeskReport = {
  role_key?: string;
  role_label?: string;
  model?: string;
  key_findings?: string[];
  metrics?: Record<string, unknown>;
  risks?: string[];
  analytical_view?: string;
  confidence_in_analysis?: number;
  error?: string | null;
};

type Props = { layer: DeliberationLayer };

function ResearchCard({ deskKey, report }: { deskKey: string; report: DeskReport }) {
  const riskN = report.risks?.length ?? 0;
  const riskLevel = riskN >= 4 ? "High" : riskN >= 2 ? "Medium" : "Low";
  const view = report.analytical_view ?? "neutral";
  const conf = report.confidence_in_analysis ?? 0;

  return (
    <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--muted))]/40 p-3">
      <div className="mb-2 text-sm font-bold">
        {report.role_label ?? deskKey.replace(/_/g, " ")}
      </div>
      <div className="flex flex-wrap gap-1.5">
        <Pill tone={stanceTone(view)}>{view} view</Pill>
        <Pill>{(conf * 100).toFixed(0)}% analysis conf</Pill>
        <Pill tone={riskLevel === "High" ? "bad" : riskLevel === "Medium" ? "warn" : "ok"}>
          {riskLevel} risks
        </Pill>
      </div>
      {report.key_findings && report.key_findings.length > 0 && (
        <ul className="mt-2 list-disc pl-4 text-xs text-slate-600 dark:text-slate-300">
          {report.key_findings.slice(0, 3).map((f, i) => (
            <li key={i}>{f}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function ResearchDesksPanel({ layer }: Props) {
  const analysis = layer.analysis_layer as { desks?: Record<string, DeskReport> } | undefined;
  const desks = analysis?.desks;
  if (!desks || Object.keys(desks).length === 0) return null;

  const entries = Object.entries(desks).filter(([, r]) => r && !r.error);
  if (entries.length === 0) return null;

  return (
    <Card className="p-4 space-y-3">
      <SectionTitle title="Research desks (analysis only)" />
      <p className="text-xs text-slate-500">
        Specialist desks produce evidence — they do not make trade decisions.
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {entries.map(([key, report]) => (
          <ResearchCard key={key} deskKey={key} report={report} />
        ))}
      </div>
    </Card>
  );
}
