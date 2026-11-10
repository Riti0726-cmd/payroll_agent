import type { ChangeListItem } from "../types/domain";
import { appendMailboxParam } from "./mailboxParam";

export class ChangeListsError extends Error {
  status: number;
  body: string;
  constructor(status: number, body: string) {
    super(describeChangeListsFailure(status, body));
    this.status = status;
    this.body = body;
  }
}

function describeChangeListsFailure(status: number, body: string): string {
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
      `Change lists unavailable (${status}). Ensure DATABASE_URL is set and the host is running, ` +
      `or set VITE_CHANGELISTS_URL to your /changelists endpoint.`
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
    return `Change lists returned ${status}: ${trimmed}`;
  }
  return `Change lists returned ${status}.`;
}

function changelistsBaseUrl(): string {
  const base = import.meta.env.VITE_CHANGELISTS_URL as string | undefined;
  if (!base) {
    throw new Error("VITE_CHANGELISTS_URL is not set");
  }
  return base;
}

export async function fetchChangeLists(
  specialistId: string,
  accessToken?: string,
): Promise<ChangeListItem[]> {
  const url = new URL(changelistsBaseUrl(), window.location.origin);
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
    throw new ChangeListsError(502, "Network error reaching the changelists API");
  }

  const body = await resp.text();
  if (!resp.ok) {
    throw new ChangeListsError(resp.status, body);
  }

  try {
    const data = JSON.parse(body) as { items?: unknown };
    if (!Array.isArray(data.items)) {
      throw new Error("missing items");
    }
    return data.items as ChangeListItem[];
  } catch {
    throw new ChangeListsError(502, `Invalid changelists response: ${body.slice(0, 200)}`);
  }
}

export async function updateChangeListStatus(
  specialistId: string,
  id: string,
  status: "approved" | "needs_clarification",
  accessToken?: string,
): Promise<ChangeListItem> {
  return patchChangeList(specialistId, id, { status }, accessToken);
}

export async function patchChangeList(
  specialistId: string,
  id: string,
  body: {
    status?: "approved" | "needs_clarification";
    lines?: ChangeListItem["lines"];
  },
  accessToken?: string,
): Promise<ChangeListItem> {
  const url = new URL(
    `${changelistsBaseUrl().replace(/\/$/, "")}/${encodeURIComponent(id)}`,
    window.location.origin,
  );
  url.searchParams.set("specialist_id", specialistId);
  appendMailboxParam(url);

  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  let resp: Response;
  try {
    resp = await fetch(url.toString(), {
      method: "PATCH",
      headers,
      body: JSON.stringify(body),
    });
  } catch {
    throw new ChangeListsError(502, "Network error reaching the changelists API");
  }

  const text = await resp.text();
  if (!resp.ok) {
    throw new ChangeListsError(resp.status, text);
  }

  try {
    return JSON.parse(text) as ChangeListItem;
  } catch {
    throw new ChangeListsError(502, `Invalid changelist response: ${text.slice(0, 200)}`);
  }
}
