export type QaChatRole = "user" | "assistant";

export type QaChatTurn = {
  role: QaChatRole;
  content: string;
};

export type QaSource = {
  label: string;
  detail?: string;
  query?: string | null;
  interpretation?: string | null;
  response?: string | null;
};

export type QaChatResponse = {
  answer: string;
  sources: QaSource[];
};

export class QaError extends Error {
  status: number;
  body: string;
  constructor(status: number, body: string) {
    super(describeQaFailure(status, body));
    this.status = status;
    this.body = body;
  }
}

function describeQaFailure(status: number, body: string): string {
  const trimmed = body.trim();
  if (status === 502 || status === 503 || status === 504) {
    return (
      `Q&A agent unreachable (${status}). Start the local host on port 8088 ` +
      `(.\.venv\\Scripts\\python.exe src\\payroll_specialist\\main.py) ` +
      `or set VITE_QA_INVOKE_URL to your /qa endpoint.`
    );
  }
  if (trimmed) {
    try {
      const parsed = JSON.parse(trimmed) as { detail?: string };
      if (parsed.detail) {
        return parsed.detail;
      }
    } catch {
      /* plain text body */
    }
    return `Q&A returned ${status}: ${trimmed}`;
  }
  return `Q&A returned ${status}.`;
}

export function formatQaSource(source: QaSource): string {
  const detail = source.detail?.trim();
  return detail ? `${source.label}: ${detail}` : source.label;
}

export function sourceHasTracePanes(source: QaSource): boolean {
  return (
    source.query != null ||
    source.interpretation != null ||
    source.response != null
  );
}

function parseSource(raw: unknown): QaSource | null {
  if (typeof raw !== "object" || raw === null) {
    return null;
  }
  const candidate = raw as Record<string, unknown>;
  if (typeof candidate.label !== "string") {
    return null;
  }
  return {
    label: candidate.label,
    detail: typeof candidate.detail === "string" ? candidate.detail : undefined,
    query: typeof candidate.query === "string" ? candidate.query : undefined,
    interpretation:
      typeof candidate.interpretation === "string"
        ? candidate.interpretation
        : undefined,
    response:
      typeof candidate.response === "string" ? candidate.response : undefined,
  };
}

export async function invokeQaChat(
  messages: QaChatTurn[],
  accessToken?: string,
): Promise<QaChatResponse> {
  const url = import.meta.env.VITE_QA_INVOKE_URL as string | undefined;
  if (!url) {
    throw new Error("VITE_QA_INVOKE_URL is not set");
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  let resp: Response;
  try {
    resp = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify({ messages }),
    });
  } catch {
    throw new QaError(
      502,
      "Network error reaching the Q&A agent (is the Vite proxy target running on :8088?)",
    );
  }

  const body = await resp.text();
  if (!resp.ok) {
    throw new QaError(resp.status, body);
  }

  try {
    const data = JSON.parse(body) as Partial<QaChatResponse>;
    if (typeof data.answer !== "string") {
      throw new Error("missing answer");
    }
    const sources = Array.isArray(data.sources)
      ? data.sources.map(parseSource).filter((s): s is QaSource => s !== null)
      : [];
    return { answer: data.answer, sources };
  } catch {
    throw new QaError(502, `Invalid Q&A response: ${body.slice(0, 200)}`);
  }
}
