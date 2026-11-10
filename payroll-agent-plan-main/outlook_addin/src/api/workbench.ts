// Email lookup, queue, drafts and change-list endpoints.
// Contracts mirror web/src/api/{queue,drafts,changelists}.ts (source of truth).
import type {
  ChangeListItem,
  ChangeListLine,
  DraftItem,
  EmailRecord,
  Priority,
  QueueItem,
} from "../types/domain";
import { ApiError, buildUrl, headers, requestJson } from "./http";

/** GET /emails/lookup — returns null when the email has not been ingested yet. */
export async function lookupEmail(
  specialistId: string,
  ids: { restId?: string; internetMessageId?: string },
  token?: string
): Promise<EmailRecord | null> {
  const url = buildUrl("/emails/lookup", specialistId, {
    rest_id: ids.restId,
    internet_message_id: ids.internetMessageId,
  });
  try {
    return await requestJson<EmailRecord>(url, { method: "GET", headers: headers(token) }, "Email");
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export async function fetchQueue(specialistId: string, token?: string): Promise<QueueItem[]> {
  const data = await requestJson<{ items?: QueueItem[] }>(
    buildUrl("/queue", specialistId),
    { method: "GET", headers: headers(token) },
    "Queue"
  );
  return Array.isArray(data.items) ? data.items : [];
}

export function patchQueueItem(
  specialistId: string,
  id: string,
  patch: { done?: boolean; priority?: Priority },
  token?: string
): Promise<QueueItem> {
  return requestJson<QueueItem>(
    buildUrl(`/queue/${encodeURIComponent(id)}`, specialistId),
    { method: "PATCH", headers: headers(token, true), body: JSON.stringify(patch) },
    "Queue"
  );
}

export function updateDraftStatus(
  specialistId: string,
  id: string,
  status: "accepted" | "discarded",
  opts?: { body?: string; token?: string }
): Promise<DraftItem> {
  const payload: { status: string; body?: string } = { status };
  if (opts?.body !== undefined) payload.body = opts.body;
  return requestJson<DraftItem>(
    buildUrl(`/drafts/${encodeURIComponent(id)}`, specialistId),
    { method: "PATCH", headers: headers(opts?.token, true), body: JSON.stringify(payload) },
    "Drafts"
  );
}

export function patchChangeList(
  specialistId: string,
  id: string,
  body: { status?: "approved" | "needs_clarification"; lines?: ChangeListLine[] },
  token?: string
): Promise<ChangeListItem> {
  return requestJson<ChangeListItem>(
    buildUrl(`/changelists/${encodeURIComponent(id)}`, specialistId),
    { method: "PATCH", headers: headers(token, true), body: JSON.stringify(body) },
    "Change lists"
  );
}
