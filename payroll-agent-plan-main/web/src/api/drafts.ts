import type { DraftItem } from "../types/domain";
import { appendMailboxParam } from "./mailboxParam";

export class DraftsError extends Error {
  status: number;
  body: string;
  constructor(status: number, body: string) {
    super(describeDraftsFailure(status, body));
    this.status = status;
    this.body = body;
  }
}

function describeDraftsFailure(status: number, body: string): string {
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
    return (
      `Drafts unavailable (${status}). Ensure DATABASE_URL is set and the host is running, ` +
      `or set VITE_DRAFTS_URL to your /drafts endpoint.`
    );
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
    return `Drafts returned ${status}: ${trimmed}`;
  }
  return `Drafts returned ${status}.`;
}

function draftsBaseUrl(): string {
  const base = import.meta.env.VITE_DRAFTS_URL as string | undefined;
  if (!base) {
    throw new Error("VITE_DRAFTS_URL is not set");
  }
  return base;
}

export async function fetchDrafts(
  specialistId: string,
  accessToken?: string,
): Promise<DraftItem[]> {
  const url = new URL(draftsBaseUrl(), window.location.origin);
  url.searchParams.set("specialist_id", specialistId);
  appendMailboxParam(url);

  const headers: Record<string, string> = { Accept: "application/json" };
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  let resp: Response;
  try {
    resp = await fetch(url.toString(), { method: "GET", headers });
  } catch {
    throw new DraftsError(502, "Network error reaching the drafts API");
  }

  const body = await resp.text();
  if (!resp.ok) {
    throw new DraftsError(resp.status, body);
  }

  try {
    const data = JSON.parse(body) as { items?: unknown };
    if (!Array.isArray(data.items)) {
      throw new Error("missing items");
    }
    return data.items as DraftItem[];
  } catch {
    throw new DraftsError(502, `Invalid drafts response: ${body.slice(0, 200)}`);
  }
}

export async function updateDraftStatus(
  specialistId: string,
  id: string,
  status: "accepted" | "discarded",
  opts?: { body?: string; token?: string },
): Promise<DraftItem> {
  const url = new URL(
    `${draftsBaseUrl().replace(/\/$/, "")}/${encodeURIComponent(id)}`,
    window.location.origin,
  );
  url.searchParams.set("specialist_id", specialistId);
  appendMailboxParam(url);

  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };
  if (opts?.token) {
    headers.Authorization = `Bearer ${opts.token}`;
  }

  const payload: { status: string; body?: string } = { status };
  if (opts?.body !== undefined) {
    payload.body = opts.body;
  }

  let resp: Response;
  try {
    resp = await fetch(url.toString(), {
      method: "PATCH",
      headers,
      body: JSON.stringify(payload),
    });
  } catch {
    throw new DraftsError(502, "Network error reaching the drafts API");
  }

  const body = await resp.text();
  if (!resp.ok) {
    throw new DraftsError(resp.status, body);
  }

  try {
    return JSON.parse(body) as DraftItem;
  } catch {
    throw new DraftsError(502, `Invalid draft response: ${body.slice(0, 200)}`);
  }
}
