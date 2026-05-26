const UTC_DATE_FORMAT = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

const UTC_TIME_FORMAT = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: "UTC",
});

/** Format an ISO timestamp as ``23 May 2026 · 21:33 UTC``. */
export function formatUtcTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const day = UTC_DATE_FORMAT.format(date);
  const time = UTC_TIME_FORMAT.format(date);
  return `${day} · ${time} UTC`;
}
