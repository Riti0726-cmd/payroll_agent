/** "hourly_pay_rate" → "Hourly pay rate". */
export function humanizeField(field: string): string {
  const text = (field || "").replace(/_/g, " ").trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "(field)";
}

/** ISO date or datetime → "Oct 16, 2026"; passes through anything unparseable. */
export function formatDate(value: string): string {
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(value);
  // Date-only strings are calendar dates; parse as local so they don't shift a day.
  const date = dateOnly ? new Date(`${value}T00:00:00`) : new Date(value);
  if (Number.isNaN(date.getTime()) || date.getFullYear() < 2000) return value;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

/** Received timestamp for list rows: "Oct 12, 9:30 AM"; empty when missing. */
export function formatReceived(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime()) || date.getFullYear() < 2000) return "";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
