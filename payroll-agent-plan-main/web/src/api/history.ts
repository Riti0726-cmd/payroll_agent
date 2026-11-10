import type { HistoryItem, HistoryStatus } from "../types/domain";
import { appendMailboxParam } from "./mailboxParam";

export class HistoryError extends Error {
  status: number;
  body: string;
  constructor(status: number, body: string) {
    super(describeHistoryFailure(status, body));
    this.status = status;
    this.body = body;
  }
}

function describeHistoryFailure(status: number, body: string): string {
  const trimmed = body.trim();
  if (status === 502 || status === 503 || status === 504) {
    if (trimmed) {
      try {
        const parsed = JSON.parse(trimmed) as { detail?: string };
        if (parsed.detail) {
          return parsed.detail;
        }
      } catch {
        /* plain text */
      }
      return trimmed;
    }
    return `History unavailable (${status}). Ensure DATABASE_URL is set and the host is running.`;
  }
  if (trimmed) {
    try {
      const parsed = JSON.parse(trimmed) as { detail?: string };
      if (parsed.detail) {
        return parsed.detail;
      }
    } catch {
      /* plain text */
    }
    return `History returned ${status}: ${trimmed}`;
  }
  return `History returned ${status}.`;
}

export async function fetchHistory(
  specialistId: string,
  status: HistoryStatus | "all" = "all",
  accessToken?: string,
): Promise<HistoryItem[]> {
  const base = import.meta.env.VITE_HISTORY_URL as string | undefined;
  if (!base) {
    throw new Error("VITE_HISTORY_URL is not set");
  }

  const url = new URL(base, window.location.origin);
  url.searchParams.set("specialist_id", specialistId);
  url.searchParams.set("status", status);
  appendMailboxParam(url);

  const headers: Record<string, string> = { Accept: "application/json" };
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  let resp: Response;
  try {
    resp = await fetch(url.toString(), { method: "GET", headers });
  } catch {
    throw new HistoryError(502, "Network error reaching the history API");
  }

  const body = await resp.text();
  if (!resp.ok) {
    throw new HistoryError(resp.status, body);
  }

  try {
    const data = JSON.parse(body) as { items?: unknown };
    if (!Array.isArray(data.items)) {
      throw new Error("missing items");
    }
    return data.items as HistoryItem[];
  } catch {
    throw new HistoryError(502, `Invalid history response: ${body.slice(0, 200)}`);
  }
}
