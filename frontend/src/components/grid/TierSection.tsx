import type { ReactNode } from "react";

type Props = {
  name: string;
  description?: string;
  children: ReactNode;
};

export function TierSection({ name, description, children }: Props) {
  return (
    <section className="flex flex-col gap-3">
      <header className="flex items-baseline justify-between gap-3 border-b border-[hsl(var(--terminal-border))] pb-2">
        <div className="flex items-baseline gap-3">
          <h2 className="text-sm font-bold uppercase tracking-[0.18em] text-[hsl(var(--terminal-text-primary))]">
            {name}
          </h2>
          {description && (
            <span className="text-[11px] uppercase tracking-wider text-[hsl(var(--terminal-text-tertiary))]">
              {description}
            </span>
          )}
        </div>
      </header>
      <div
        className="grid gap-3"
        style={{ gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))" }}
      >
        {children}
      </div>
    </section>
  );
}
