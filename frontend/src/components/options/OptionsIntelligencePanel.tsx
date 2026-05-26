import type { ReactNode } from "react";
import { Card } from "@/components/ui/card";
import type { OptionsIntelligence } from "@/types/schemas";

type Props = {
  options: OptionsIntelligence;
};

type Tone = "ok" | "warn" | "bad" | "neutral";

function Pill({ children, tone }: { children: ReactNode; tone?: Tone }) {
  const cls =
    tone === "ok"
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200"
      : tone === "warn"
        ? "border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-100"
        : tone === "bad"
          ? "border-rose-500/30 bg-rose-500/10 text-rose-800 dark:text-rose-200"
          : "border-[hsl(var(--border))] bg-[hsl(var(--muted))] text-slate-700 dark:text-slate-200";
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${cls}`}>
      {children}
    </span>
  );
}

function SectionTitle({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-2 flex items-baseline justify-between gap-2">
      <h2 className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
        {title}
      </h2>
      {children}
    </div>
  );
}

function labelTone(label: string): Tone {
  const l = label.toUpperCase();
  if (l === "SAFE" || l === "LOW") return "ok";
  if (l === "CAUTION" || l === "MEDIUM") return "warn";
  if (l === "UNSAFE" || l === "HIGH") return "bad";
  return "neutral";
}

function safetyTone(score: number): Tone {
  if (score >= 7) return "ok";
  if (score >= 4) return "warn";
  return "bad";
}

function fmtPct(p: number): string {
  return `${Math.round(p * 100)}%`;
}

function fmtSigned(pct: number): string {
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

function MetricCell({
  label,
  value,
  hint,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
}) {
  return (
    <div className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--card))] px-3 py-2">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-slate-50">{value}</div>
      {hint && <div className="mt-0.5 text-[11px] text-slate-500">{hint}</div>}
    </div>
  );
}

export function OptionsIntelligencePanel({ options }: Props) {
  const {
    source,
    horizon_days,
    last_close,
    daily_vol_pct,
    expected_range,
    move_probabilities,
    pin_risk,
    body_danger,
    event_risk,
    credit_safety,
    reverse_bwb,
    disclaimer,
  } = options;

  const downsidePct = ((expected_range.low - last_close) / last_close) * 100;
  const upsidePct = ((expected_range.high - last_close) / last_close) * 100;

  return (
    <Card className="border-indigo-500/25 p-4 dark:border-indigo-400/25">
      <SectionTitle title="3.5 · Options intelligence">
        <span className="flex items-center gap-2">
          <Pill tone={source === "live_iv" ? "ok" : "neutral"}>
            {source === "live_iv" ? "IV-backed" : "Realized-vol"}
          </Pill>
          <Pill>Horizon {horizon_days}d</Pill>
        </span>
      </SectionTitle>

      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-lg border-2 border-dashed border-[hsl(var(--border))] px-4 py-3">
          <div className="text-[11px] font-semibold uppercase text-slate-500">Credit Safety</div>
          <div className="mt-1 flex items-baseline gap-2">
            <span
              className={`font-mono text-3xl font-bold ${
                safetyTone(credit_safety.score) === "ok"
                  ? "text-emerald-600 dark:text-emerald-300"
                  : safetyTone(credit_safety.score) === "warn"
                    ? "text-amber-700 dark:text-amber-200"
                    : "text-rose-600 dark:text-rose-300"
              }`}
            >
              {credit_safety.score.toFixed(1)}
            </span>
            <span className="text-xs text-slate-500">/ 10</span>
          </div>
          <div className="mt-1">
            <Pill tone={labelTone(credit_safety.label)}>{credit_safety.label}</Pill>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-1 text-[10px] text-slate-500">
            <span>
              prob block <strong className="text-slate-700 dark:text-slate-300">{fmtPct(credit_safety.components.prob_block)}</strong>
            </span>
            <span>
              vol regime <strong className="text-slate-700 dark:text-slate-300">{fmtPct(credit_safety.components.vol_regime)}</strong>
            </span>
            <span>
              pin <strong className="text-slate-700 dark:text-slate-300">{fmtPct(credit_safety.components.pin_risk)}</strong>
            </span>
            <span>
              body <strong className="text-slate-700 dark:text-slate-300">{fmtPct(credit_safety.components.body_danger)}</strong>
            </span>
            <span>
              event <strong className="text-slate-700 dark:text-slate-300">{fmtPct(credit_safety.components.event_risk)}</strong>
            </span>
          </div>
        </div>

        <div className="rounded-lg border border-[hsl(var(--border))] px-4 py-3">
          <div className="text-[11px] font-semibold uppercase text-slate-500">Expected range ({horizon_days}d, 1σ)</div>
          <div className="mt-1 font-mono text-2xl font-semibold text-slate-900 dark:text-slate-50">
            {expected_range.low.toFixed(2)}
            <span className="mx-2 text-slate-400">–</span>
            {expected_range.high.toFixed(2)}
          </div>
          <div className="mt-1 flex flex-wrap gap-1.5">
            <Pill>σ {expected_range.sigma_pct.toFixed(2)}%</Pill>
            <Pill>confidence {fmtPct(expected_range.confidence)}</Pill>
            <Pill tone="bad">{fmtSigned(downsidePct)}</Pill>
            <Pill tone="ok">{fmtSigned(upsidePct)}</Pill>
          </div>
        </div>

        <div className="rounded-lg border border-[hsl(var(--border))] px-4 py-3">
          <div className="text-[11px] font-semibold uppercase text-slate-500">Reverse-BWB suitability</div>
          <div className="mt-1 flex items-baseline gap-2">
            <span
              className={`font-mono text-2xl font-bold ${
                safetyTone(reverse_bwb.score) === "ok"
                  ? "text-emerald-600 dark:text-emerald-300"
                  : safetyTone(reverse_bwb.score) === "warn"
                    ? "text-amber-700 dark:text-amber-200"
                    : "text-rose-600 dark:text-rose-300"
              }`}
            >
              {reverse_bwb.score.toFixed(1)}
            </span>
            <span className="text-xs text-slate-500">/ 10</span>
            <Pill tone={labelTone(reverse_bwb.label)}>{reverse_bwb.label}</Pill>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Pill>Wing {reverse_bwb.suggested_wing_width_pct.toFixed(2)}%</Pill>
            <Pill>DTE {reverse_bwb.suggested_dte}</Pill>
          </div>
          <p className="mt-2 text-[11px] leading-snug text-slate-600 dark:text-slate-400">{reverse_bwb.rationale}</p>
        </div>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCell
          label="P up ≥ 2%"
          value={fmtPct(move_probabilities.p_up_2pct)}
          hint={`P up ≥ 3% ${fmtPct(move_probabilities.p_up_3pct)}`}
        />
        <MetricCell
          label="P down ≥ 2%"
          value={fmtPct(move_probabilities.p_dn_2pct)}
          hint={`P down ≥ 3% ${fmtPct(move_probabilities.p_dn_3pct)}`}
        />
        <MetricCell
          label="P inside 1σ band"
          value={fmtPct(move_probabilities.p_in_range_1sigma)}
          hint="probability of staying in the expected range"
        />
        <MetricCell
          label="Pin risk"
          value={
            <span className="flex items-center gap-2">
              <Pill tone={labelTone(pin_risk.label)}>{pin_risk.label}</Pill>
              <span className="font-mono text-xs text-slate-500">{pin_risk.nearest_round.toFixed(2)}</span>
            </span>
          }
          hint={`distance ${pin_risk.distance_pct.toFixed(2)}%`}
        />
        <MetricCell
          label="Event risk"
          value={<Pill tone={labelTone(event_risk.label)}>{event_risk.label}</Pill>}
          hint={(event_risk.drivers ?? []).slice(0, 2).join(" · ") || "no scheduled drivers"}
        />
      </div>

      <div className="mt-3 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--muted))] p-3 text-[11px] text-slate-600 dark:text-slate-300">
        <span className="font-semibold">Body danger zone </span>
        {body_danger.short_body_lo.toFixed(2)} – {body_danger.short_body_hi.toFixed(2)} ·{" "}
        <Pill tone={labelTone(body_danger.label)}>{body_danger.label}</Pill>
        <span className="ml-2 text-slate-500">
          spot {last_close.toFixed(2)} · daily vol {daily_vol_pct.toFixed(2)}%
        </span>
      </div>

      <p className="mt-2 text-[10px] text-slate-500">{disclaimer ?? "Probability model from realized volatility; not financial advice."}</p>
    </Card>
  );
}
