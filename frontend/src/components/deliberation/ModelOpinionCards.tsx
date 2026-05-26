import { Card } from "@/components/ui/card";
import type { DeliberationLayer, IndependentOpinion } from "@/types/schemas";
import {
  CORE_DESK_KEYS,
  SPECIALIZED_DESK_KEYS,
  deskLabel,
  modelTooltip,
  Pill,
  SectionTitle,
  stanceTone,
} from "./shared";

type Props = { layer: DeliberationLayer };

function OpinionCard({ deskKey, op }: { deskKey: string; op: IndependentOpinion }) {
  const riskN = (op.key_risks?.length ?? 0) + (op.hidden_assumptions?.length ?? 0);
  const riskLevel = riskN >= 6 ? "High" : riskN >= 3 ? "Medium" : "Low";
  return (
    <div
      className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--muted))]/40 p-3"
      title={modelTooltip(deskKey, op.role_label, op.model)}
    >
      <div className="mb-2 text-sm font-bold">{deskLabel(deskKey, op.role_label)}</div>
      <div className="flex flex-wrap gap-1.5">
        <Pill tone={stanceTone(op.stance)}>{op.stance}</Pill>
        <Pill>{(op.confidence * 100).toFixed(0)}% conf</Pill>
        <Pill tone={riskLevel === "High" ? "bad" : riskLevel === "Medium" ? "warn" : "ok"}>
          {riskLevel} risk
        </Pill>
      </div>
      {op.time_horizon && (
        <p className="mt-2 text-xs text-slate-500">Horizon: {op.time_horizon}</p>
      )}
      {op.provider_attempts && op.provider_attempts.length > 1 && (
        <p className="mt-1 text-[10px] text-slate-400">
          Failover: {op.provider_attempts.join(" → ")}
        </p>
      )}
    </div>
  );
}

function DeskGroup({
  title,
  round1,
  keys,
}: {
  title: string;
  round1: Record<string, IndependentOpinion>;
  keys: readonly string[];
}) {
  const entries = keys
    .map((k) => [k, round1[k]] as const)
    .filter(([, op]) => op && !op.error);
  if (entries.length === 0) return null;
  return (
    <div>
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">{title}</p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {entries.map(([key, op]) => (
          <OpinionCard key={key} deskKey={key} op={op} />
        ))}
      </div>
    </div>
  );
}

export function ModelOpinionCards({ layer }: Props) {
  const round1 = layer.round1 ?? {};
  const known = new Set([...CORE_DESK_KEYS, ...SPECIALIZED_DESK_KEYS]);
  const otherKeys = Object.keys(round1).filter((k) => !known.has(k as (typeof CORE_DESK_KEYS)[number]));

  return (
    <Card className="p-4 space-y-4">
      <SectionTitle title="Desk panel views" />
      <DeskGroup title="Core desks" round1={round1} keys={CORE_DESK_KEYS} />
      <DeskGroup title="Specialized desks" round1={round1} keys={SPECIALIZED_DESK_KEYS} />
      {otherKeys.length > 0 && (
        <DeskGroup title="Other" round1={round1} keys={otherKeys} />
      )}
    </Card>
  );
}
