import type { Priority, QueueItem } from "../types/domain";
import { appendMailboxParam } from "./mailboxParam";

export class QueueError extends Error {
  status: number;
  body: string;
  constructor(status: number, body: string) {
    super(describeQueueFailure(status, body));
    this.status = status;
    this.body = body;
  }
}

function describeQueueFailure(status: number, body: string): string {
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
      `Queue unavailable (${status}). Ensure DATABASE_URL is set and the host is running ` +
      `(.\.venv\\Scripts\\python.exe src\\payroll_specialist\\main.py), ` +
      `or set VITE_QUEUE_URL to your /queue endpoint.`
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
    return `Queue returned ${status}: ${trimmed}`;
  }
  return `Queue returned ${status}.`;
}

function queueBaseUrl(): string {
  const base = import.meta.env.VITE_QUEUE_URL as string | undefined;
  if (!base) {
    throw new Error("VITE_QUEUE_URL is not set");
  }
  return base;
}

function authHeaders(accessToken?: string): Record<string, string> {
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }
  return headers;
}

export async function fetchQueue(
  specialistId: string,
  accessToken?: string,
): Promise<QueueItem[]> {
  const url = new URL(queueBaseUrl(), window.location.origin);
  url.searchParams.set("specialist_id", specialistId);
  appendMailboxParam(url);

  let resp: Response;
  try {
    resp = await fetch(url.toString(), {
      method: "GET",
      headers: authHeaders(accessToken),
    });
  } catch {
    throw new QueueError(
      502,
      "Network error reaching the queue API (is the Vite proxy target running on :8088?)",
    );
  }

  const body = await resp.text();
  if (!resp.ok) {
    throw new QueueError(resp.status, body);
  }

  try {
    const data = JSON.parse(body) as { items?: unknown };
    if (!Array.isArray(data.items)) {
      throw new Error("missing items");
    }
    return data.items as QueueItem[];
  } catch {
    throw new QueueError(502, `Invalid queue response: ${body.slice(0, 200)}`);
  }
}

export async function patchQueueItem(
  specialistId: string,
  id: string,
  patch: { done?: boolean; priority?: Priority },
  accessToken?: string,
): Promise<QueueItem> {
  const url = new URL(
    `${queueBaseUrl().replace(/\/$/, "")}/${encodeURIComponent(id)}`,
    window.location.origin,
  );
  url.searchParams.set("specialist_id", specialistId);
  appendMailboxParam(url);

  const payload: { done?: boolean; priority?: number } = {};
  if (patch.done !== undefined) {
    payload.done = patch.done;
  }
  if (patch.priority !== undefined) {
    payload.priority = patch.priority;
  }

  let resp: Response;
  try {
    resp = await fetch(url.toString(), {
      method: "PATCH",
      headers: {
        ...authHeaders(accessToken),
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new QueueError(502, "Network error reaching the queue API");
  }

  const body = await resp.text();
  if (!resp.ok) {
    throw new QueueError(resp.status, body);
  }

  try {
    return JSON.parse(body) as QueueItem;
  } catch {
    throw new QueueError(502, `Invalid queue patch response: ${body.slice(0, 200)}`);
  }
}
