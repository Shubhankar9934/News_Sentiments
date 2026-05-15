type Props = { url?: string; headline?: string };

export function VerificationPanel({ url, headline }: Props) {
  const title = headline?.trim() ?? "";
  const safe = url?.trim();
  if (!safe) {
    return (
      <p className="text-xs text-amber-700 dark:text-amber-300">
        No direct URL on file for this headline — cross-check in your data vendor.
      </p>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      <a
        href={safe}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--card))] px-2 py-1 text-xs font-medium text-indigo-600 underline-offset-2 hover:underline dark:text-indigo-400"
      >
        Open original article
      </a>
      <span className="text-[10px] text-slate-500">
        {title.length > 80 ? `${title.slice(0, 80)}…` : title || "(no headline)"}
      </span>
    </div>
  );
}
