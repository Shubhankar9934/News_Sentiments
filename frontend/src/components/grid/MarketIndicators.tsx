import { Chip, SectionFrame } from "@/components/grid/primitives";
import { toneFor } from "@/lib/deriveDecisionTone";
import type { ExecutiveSummary } from "@/types/schemas";

type Row = { label: string; value: string | null };

export function MarketIndicators({ summary }: { summary: ExecutiveSummary | null }) {
  const rows: Row[] = [
    { label: "Event Risk", value: summary?.event_risk ?? null },
    { label: "IV Quality", value: summary?.iv_quality ?? null },
    { label: "Liquidity", value: summary?.liquidity ?? null },
    { label: "Pin Risk", value: summary?.pin_risk ?? null },
  ];
  return (
    <SectionFrame title="Risk Indicators">
      <div className="grid grid-cols-2 gap-2">
        {rows.map((row) => (
          <div
            key={row.label}
            className="flex items-center justify-between gap-2 rounded-md border border-[hsl(var(--terminal-border))] bg-[hsl(var(--terminal-card-elevated))]/50 px-3 py-1.5"
          >
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--terminal-text-secondary))]">
              {row.label}
            </span>
            <Chip tone={toneFor(row.value)}>{row.value ?? "—"}</Chip>
          </div>
        ))}
      </div>
    </SectionFrame>
  );
}
