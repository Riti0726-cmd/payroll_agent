// Shared fetch helpers. Request/response contracts mirror web/src/api/* (source of truth).
import { apiUrl, config } from "../config";

export class ApiError extends Error {
  status: number;
  body: string;
  constructor(status: number, body: string, fallback?: string) {
    super(describeFailure(status, body, fallback));
    this.status = status;
    this.body = body;
  }
}

function describeFailure(status: number, body: string, fallback?: string): string {
  const trimmed = body.trim();
  if (trimmed) {
    try {
      const parsed = JSON.parse(trimmed) as { detail?: string };
      if (parsed.detail) return parsed.detail;
    } catch {
      /* plain text */
    }
    return trimmed.slice(0, 300);
  }
  return fallback ?? `Request failed (${status}).`;
}

type FetchInit = Parameters<typeof fetch>[1];

export type Query = Record<string, string | undefined>;

/** Build a backend URL with specialist_id, optional mailbox override and extra params. */
export function buildUrl(path: string, specialistId: string, query: Query = {}): URL {
  const url = apiUrl(path);
  url.searchParams.set("specialist_id", specialistId);
  if (config.mailboxOverride) {
    url.searchParams.set("mailbox", config.mailboxOverride);
  }
  for (const [key, value] of Object.entries(query)) {
    if (value) url.searchParams.set(key, value);
  }
  return url;
}

export function headers(token?: string, json = false): Record<string, string> {
  const out: Record<string, string> = { Accept: "application/json" };
  if (json) out["Content-Type"] = "application/json";
  if (token) out.Authorization = `Bearer ${token}`;
  return out;
}

export async function requestJson<T>(url: URL, init: FetchInit, label: string): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(url.toString(), init);
  } catch {
    throw new ApiError(502, "", `Network error reaching the ${label} API. Is the backend running?`);
  }
  const text = await resp.text();
  if (!resp.ok) {
    throw new ApiError(resp.status, text, `${label} returned ${resp.status}.`);
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new ApiError(502, "", `Invalid ${label} response.`);
  }
}
