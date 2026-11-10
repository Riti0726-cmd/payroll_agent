// QA chat and triage-run SSE streams. Event shapes mirror web/src/api/{qa,triage}.ts.
import { apiUrl } from "../config";
import { ApiError, buildUrl } from "./http";
import { readSseStream } from "./sse";

export type QaChatTurn = { role: "user" | "assistant"; content: string };

export type QaSource = {
  label: string;
  detail?: string;
  query?: string | null;
  interpretation?: string | null;
  response?: string | null;
};

export type QaResult = { answer: string; sources: QaSource[] };

export type QaProgressEvent =
  | { type: "started" }
  | { type: "tool_started" | "tool_finished"; name: string; label: string }
  | { type: "finished"; answer: string; sources: QaSource[] }
  | { type: "error"; message: string };

function toSources(raw: unknown): QaSource[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((s): s is Record<string, unknown> => typeof s === "object" && s !== null)
    .filter((s) => typeof s.label === "string")
    .map((s) => ({
      label: s.label as string,
      detail: typeof s.detail === "string" ? s.detail : undefined,
      query: typeof s.query === "string" ? s.query : undefined,
      interpretation: typeof s.interpretation === "string" ? s.interpretation : undefined,
      response: typeof s.response === "string" ? s.response : undefined,
    }));
}

export function toQaEvent(type: string, payload: Record<string, unknown>): QaProgressEvent | null {
  if (type === "started") return { type: "started" };
  if (type === "tool_started" || type === "tool_finished") {
    const name = typeof payload.name === "string" ? payload.name : "";
    const label = typeof payload.label === "string" ? payload.label : name || "Working…";
    return { type, name, label };
  }
  if (type === "finished" && typeof payload.answer === "string") {
    return { type: "finished", answer: payload.answer, sources: toSources(payload.sources) };
  }
  if (type === "error") {
    return {
      type: "error",
      message: typeof payload.message === "string" ? payload.message : "Q&A stream error",
    };
  }
  return null;
}

/** POST /qa/stream — resolves with the final answer, emitting progress events. */
export async function askQa(
  messages: QaChatTurn[],
  token: string | undefined,
  onEvent: (event: QaProgressEvent) => void,
  signal?: AbortSignal
): Promise<QaResult> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  let resp: Response;
  try {
    resp = await fetch(apiUrl("/qa/stream").toString(), {
      method: "POST",
      headers,
      body: JSON.stringify({ messages }),
      signal,
    });
  } catch {
    throw new ApiError(502, "", "Network error reaching the Q&A agent. Is the backend running?");
  }
  if (!resp.ok) throw new ApiError(resp.status, await resp.text());

  let result: QaResult | null = null;
  let streamError: string | null = null;
  await readSseStream(resp, (type, payload) => {
    const event = toQaEvent(type, payload);
    if (!event) return;
    onEvent(event);
    if (event.type === "finished") result = { answer: event.answer, sources: event.sources };
    if (event.type === "error") streamError = event.message;
  });
  if (streamError) throw new ApiError(502, "", streamError);
  if (!result) throw new ApiError(502, "", "Q&A stream ended without an answer.");
  return result;
}

export type TriageProgressEvent =
  | { type: "run_started"; runId: string; mailbox: string; total: number }
  | { type: "email_started"; index: number; total: number; messageId: string; subject: string }
  | {
      type: "email_finished";
      index: number;
      total: number;
      messageId: string;
      subject: string;
      status: string;
      category?: string | null;
      error?: string;
    }
  | {
      type: "run_finished";
      runId: string;
      succeeded: number;
      failed: number;
      skipped: number;
      summary: string;
    }
  | { type: "error"; message: string };

/** POST /triage/stream — needs a delegated Graph Mail.Read token. */
export async function runTriage(
  specialistId: string,
  graphToken: string,
  onEvent: (event: TriageProgressEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  let resp: Response;
  try {
    resp = await fetch(buildUrl("/triage/stream", specialistId).toString(), {
      method: "POST",
      headers: { Authorization: `Bearer ${graphToken}`, Accept: "text/event-stream" },
      signal,
    });
  } catch {
    throw new ApiError(502, "", "Network error reaching the triage stream.");
  }
  if (!resp.ok) throw new ApiError(resp.status, await resp.text());
  await readSseStream(resp, (type, payload) => {
    onEvent({ ...payload, type } as TriageProgressEvent);
  });
}
