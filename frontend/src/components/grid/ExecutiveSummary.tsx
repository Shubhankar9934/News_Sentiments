import { SectionFrame } from "@/components/grid/primitives";
import { cn } from "@/lib/utils";

type Props = {
  text: string | null;
  loading?: boolean;
  version?: number;
};

export function ExecutiveSummary({ text, loading, version }: Props) {
  return (
    <SectionFrame
      title="Executive Summary"
      trailing={
        version === 2 ? (
          <span className="text-[9px] font-bold uppercase tracking-wider text-emerald-400/80">
            DIL-backed
          </span>
        ) : version === 1 ? (
          <span className="text-[9px] font-bold uppercase tracking-wider text-[hsl(var(--terminal-text-tertiary))]">
            Options-only
          </span>
        ) : null
      }
    >
      <p
        className={cn(
          "min-h-[64px] text-[12px] leading-snug text-slate-300",
          loading && "animate-pulse text-slate-500",
        )}
        style={{
          display: "-webkit-box",
          WebkitLineClamp: 4,
          WebkitBoxOrient: "vertical",
          overflow: "hidden",
        }}
      >
        {text ?? "Run analysis to populate trader summary."}
      </p>
    </SectionFrame>
  );
}
