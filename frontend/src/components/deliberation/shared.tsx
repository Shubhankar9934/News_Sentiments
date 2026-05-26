import type { ReactNode } from "react";

export function SectionTitle({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-2 flex items-baseline justify-between gap-2">
      <h3 className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
        {title}
      </h3>
      {children}
    </div>
  );
}

export function Pill({
  children,
  tone,
}: {
  children: ReactNode;
  tone?: "ok" | "warn" | "bad" | "neutral";
}) {
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

export function stanceTone(stance: string): "ok" | "warn" | "bad" | "neutral" {
  const s = stance.toLowerCase();
  if (s.includes("bull")) return "ok";
  if (s.includes("bear")) return "bad";
  return "neutral";
}

export const MODEL_LABELS: Record<string, string> = {
  gpt: "GPT",
  claude: "Claude",
  gemini: "Gemini",
  deepseek: "DeepSeek",
  groq: "Groq",
};

/** Desk labels keyed by role_key (canonical) or legacy model key. */
export const DESK_LABELS_BY_KEY: Record<string, string> = {
  macro_desk: "Macro Desk",
  fundamental_desk: "Fundamental Desk",
  options_desk: "Options Desk",
  risk_desk: "Risk Desk",
  devils_advocate_desk: "Devil's Advocate Desk",
  technical_desk: "Technical Desk",
  news_desk: "News Intelligence Desk",
  earnings_desk: "Earnings Desk",
  event_risk_desk: "Event Risk Desk",
  flow_desk: "Flow Desk",
  liquidity_desk: "Liquidity Desk",
  regime_desk: "Regime Desk",
  quant_desk: "Quant Desk",
  reverse_bwb_structure_desk: "Reverse BWB Structure Desk",
  // Legacy model-key mapping
  gpt: "Macro Desk",
  claude: "Fundamental Desk",
  gemini: "Devil's Advocate Desk",
  deepseek: "Risk Desk",
  groq: "Options Desk",
};

export const CORE_DESK_KEYS = [
  "macro_desk",
  "fundamental_desk",
  "options_desk",
  "risk_desk",
  "devils_advocate_desk",
] as const;

export const SPECIALIZED_DESK_KEYS = [
  "technical_desk",
  "news_desk",
  "earnings_desk",
  "event_risk_desk",
  "flow_desk",
  "liquidity_desk",
  "regime_desk",
  "quant_desk",
  "reverse_bwb_structure_desk",
] as const;

/** @deprecated use DESK_LABELS_BY_KEY */
export const DESK_LABELS = DESK_LABELS_BY_KEY;

export function deskLabel(deskKey: string, roleLabel?: string | null): string {
  if (roleLabel && roleLabel.trim().length > 0) return roleLabel;
  return DESK_LABELS_BY_KEY[deskKey] ?? deskKey.replace(/_/g, " ");
}

export function modelTooltip(deskKey: string, roleLabel?: string | null, provider?: string | null): string {
  const desk = deskLabel(deskKey, roleLabel);
  const m = provider ?? (MODEL_LABELS[deskKey] ? deskKey : null);
  const providerLabel = m ? MODEL_LABELS[m] ?? m : null;
  if (!providerLabel || desk === providerLabel) return desk;
  return `${desk} (powered by ${providerLabel})`;
}
