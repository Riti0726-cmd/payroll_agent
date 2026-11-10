import { invokeFoundry, triageRunInput } from "./foundry";

export type TriageProgressEvent =
  | {
      type: "run_started";
      runId: string;
      mailbox: string;
      total: number;
    }
  | {
      type: "email_started";
      index: number;
      total: number;
      messageId: string;
      subject: string;
    }
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
  | {
      type: "error";
      message: string;
    };

export class TriageStreamError extends Error {
  status: number;
  body: string;
  constructor(status: number, body: string) {
    super(body || `Triage stream failed (${status})`);
    this.status = status;
    this.body = body;
  }
}

function triageStreamUrl(): string {
  return (import.meta.env.VITE_TRIAGE_STREAM_URL as string | undefined) || "/api/triage/stream";
}

/** Legacy Foundry blocking triage (kept for fallback / hosted agents). */
export async function runTriage(specialistId: string, token?: string) {
  return invokeFoundry(triageRunInput(specialistId), token);
}

function parseSseChunk(
  buffer: string,
  onEvent: (event: TriageProgressEvent) => void,
): string {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  for (const part of parts) {
    if (!part.trim()) continue;
    let eventType = "message";
    const dataLines: string[] = [];
    for (const line of part.split("\n")) {
      if (line.startsWith("event:")) {
        eventType = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    }
    if (dataLines.length === 0) continue;
    try {
      const payload = JSON.parse(dataLines.join("\n")) as TriageProgressEvent;
      if (!payload.type) {
        (payload as { type: string }).type = eventType;
      }
      onEvent(payload);
    } catch {
      /* ignore malformed frames */
    }
  }
  return rest;
}

export async function runTriageStream(
  specialistId: string,
  token: string,
  onEvent: (event: TriageProgressEvent) => void,
  opts?: { mailbox?: string; signal?: AbortSignal },
): Promise<TriageProgressEvent | null> {
  const url = new URL(triageStreamUrl(), window.location.origin);
  url.searchParams.set("specialist_id", specialistId);
  if (opts?.mailbox) {
    url.searchParams.set("mailbox", opts.mailbox);
  }

  let resp: Response;
  try {
    resp = await fetch(url.toString(), {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "text/event-stream",
      },
      signal: opts?.signal,
    });
  } catch {
    throw new TriageStreamError(502, "Network error reaching the triage stream");
  }

  if (!resp.ok) {
    const body = await resp.text();
    throw new TriageStreamError(resp.status, body || `Triage stream returned ${resp.status}`);
  }

  if (!resp.body) {
    throw new TriageStreamError(502, "Triage stream returned an empty body");
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let last: TriageProgressEvent | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    buffer = parseSseChunk(buffer, (event) => {
      last = event;
      onEvent(event);
    });
  }
  if (buffer.trim()) {
    parseSseChunk(`${buffer}\n\n`, (event) => {
      last = event;
      onEvent(event);
    });
  }
  return last;
}
