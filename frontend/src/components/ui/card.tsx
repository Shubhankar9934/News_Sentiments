import * as React from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-lg border border-[hsl(var(--border))] bg-white/60 p-4 shadow-sm dark:bg-slate-950/40", className)}
      {...props}
    />
  );
}
