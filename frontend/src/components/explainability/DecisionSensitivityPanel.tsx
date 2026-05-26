import type { Explainability } from "@/types/schemas";
import { ExplainCard } from "./shared";
import { Pill } from "@/components/deliberation/shared";

type Sensitivity = NonNullable<Explainability["decision_sensitivity"]>;
type Driver = Sensitivity["key_drivers"][number];
type Assumption = Sensitivity["assumptions"][number];
type Trigger = Sensitivity["triggers"][number];
type Stance = NonNullable<Sensitivity["analyst_disagreement"]>["stances"][number];

function decisionTone(decision: string): "ok" | "warn" | "bad" | "neutral" {
  const d = decision.toUpperCase();
  if (d === "ENTER") return "ok";
  if (d === "WAIT") return "warn";
  if (d === "AVOID") return "bad";
  return "neutral";
}

function directionTone(
  direction: Driver["direction"],
): "ok" | "warn" | "bad" | "neutral" {
  if (direction === "supports") return "bad";
  if (direction === "opposes") return "ok";
  return "neutral";
}

function fragilityTone(
  fragility: Assumption["fragility"],
): "ok" | "warn" | "bad" | "neutral" {
  if (fragility === "low") return "ok";
  if (fragility === "high") return "bad";
  return "warn";
}

function stanceTone(stance: Stance["stance"]): "ok" | "warn" | "bad" | "neutral" {
  if (stance === "Bullish") return "ok";
  if (stance === "Bearish") return "bad";
  return "warn";
}

function KeyDriversList({ drivers }: { drivers: Driver[] }) {
  if (drivers.length === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      <div className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
        Key Drivers (attribution of the decision)
      </div>
      <div className="flex flex-col gap-2">
        {drivers.map((driver) => (
          <div
            key={driver.label}
            className="flex flex-col gap-1 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--muted))] px-3 py-2"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-200">
                {driver.label}
              </span>
              <div className="flex items-center gap-2">
                <Pill tone={directionTone(driver.direction)}>
                  {driver.direction}
                </Pill>
                <Pill tone="neutral">{driver.weight_pct.toFixed(0)}%</Pill>
              </div>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-[hsl(var(--border))]">
              <div
                className={
                  "h-full rounded-full " +
                  (driver.direction === "supports"
                    ? "bg-rose-500/70"
                    : driver.direction === "opposes"
                      ? "bg-emerald-500/70"
                      : "bg-slate-400/70")
                }
                style={{ width: `${Math.min(100, driver.weight_pct)}%` }}
              />
            </div>
            {driver.detail && (
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {driver.detail}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function AssumptionList({ assumptions }: { assumptions: Assumption[] }) {
  if (assumptions.length === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      <div className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
        Critical Assumptions
      </div>
      <ul className="flex flex-col gap-1.5">
        {assumptions.map((a) => (
          <li
            key={a.label}
            className="flex flex-col gap-0.5 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--muted))] px-3 py-2"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-200">
                {a.label}
              </span>
              <Pill tone={fragilityTone(a.fragility)}>
                fragility: {a.fragility}
              </Pill>
            </div>
            {a.basis && (
              <span className="text-xs text-slate-500 dark:text-slate-400">
                {a.basis}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function TriggerList({ triggers }: { triggers: Trigger[] }) {
  if (triggers.length === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      <div className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
        What would change the decision?
      </div>
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
        {triggers.map((t) => (
          <div
            key={t.target_decision}
            className="flex flex-col gap-1 rounded-md border border-[hsl(var(--border))] px-3 py-2"
          >
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
                Decision flips to
              </span>
              <Pill tone={decisionTone(t.target_decision)}>
                {t.target_decision.toUpperCase()}
              </Pill>
            </div>
            <ul className="ml-4 mt-1 list-disc text-sm text-slate-700 dark:text-slate-200">
              {t.conditions.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

function DisagreementPanel({
  data,
}: {
  data: NonNullable<Sensitivity["analyst_disagreement"]>;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
          Where Analysts Disagreed
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {Object.entries(data.stance_counts).map(([stance, count]) => (
            <Pill key={stance} tone={stanceTone(stance as Stance["stance"])}>
              {stance}: {count}
            </Pill>
          ))}
          {data.converged && <Pill tone="ok">Converged</Pill>}
        </div>
      </div>

      {data.stances.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
                <th className="py-1">Member</th>
                <th className="py-1">Stance</th>
                <th className="py-1">Risk</th>
                <th className="py-1">Confidence</th>
                <th className="py-1">Headline</th>
              </tr>
            </thead>
            <tbody>
              {data.stances.map((row) => (
                <tr
                  key={row.member}
                  className="border-t border-[hsl(var(--border))]"
                >
                  <td className="py-1 pr-2 font-medium text-slate-700 dark:text-slate-200">
                    {row.label}
                  </td>
                  <td className="py-1 pr-2">
                    <Pill tone={stanceTone(row.stance)}>{row.stance}</Pill>
                  </td>
                  <td className="py-1 pr-2 text-slate-600 dark:text-slate-300">
                    {row.risk_view ?? "—"}
                  </td>
                  <td className="py-1 pr-2 text-slate-600 dark:text-slate-300">
                    {row.confidence_view ?? "—"}
                  </td>
                  <td className="py-1 text-slate-600 dark:text-slate-300">
                    {row.headline ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data.main_conflict && (
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Main conflict: <span className="font-medium">{data.main_conflict}</span>
        </p>
      )}
    </div>
  );
}

export function DecisionSensitivityPanel({ data }: { data: Sensitivity }) {
  return (
    <ExplainCard
      title="Decision Sensitivity Analysis"
      subtitle={`What drives, supports and could flip ${data.current_decision.toUpperCase()}`}
    >
      <KeyDriversList drivers={data.key_drivers} />
      <AssumptionList assumptions={data.assumptions} />
      <TriggerList triggers={data.triggers} />
      {data.analyst_disagreement && (
        <DisagreementPanel data={data.analyst_disagreement} />
      )}
    </ExplainCard>
  );
}
