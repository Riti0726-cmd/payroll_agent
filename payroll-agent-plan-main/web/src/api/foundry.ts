export class FoundryError extends Error {
  status: number;
  body: string;
  constructor(status: number, body: string) {
    super(describeFoundryFailure(status, body));
    this.status = status;
    this.body = body;
  }
}

function describeFoundryFailure(status: number, body: string): string {
  const trimmed = body.trim();
  if (status === 502 || status === 503 || status === 504) {
    return (
      `Agent unreachable (${status}). Start the local host on port 8088 ` +
      `(.\.venv\\Scripts\\python.exe src\\payroll_specialist\\main.py) ` +
      `or set VITE_FOUNDRY_INVOKE_URL to your deployed Foundry invoke URL.`
    );
  }
  return trimmed
    ? `Foundry returned ${status}: ${trimmed}`
    : `Foundry returned ${status}.`;
}

function isClassifierJson(text: string): boolean {
  if (!text.startsWith("{")) {
    return false;
  }
  try {
    const parsed = JSON.parse(text) as { category?: unknown };
    return typeof parsed === "object" && parsed !== null && "category" in parsed;
  } catch {
    return false;
  }
}

function isNoisyWrap(text: string): boolean {
  return (
    text.includes("[{'type':") ||
    text.includes('[{"type":') ||
    text.includes("'phase': 'final_answer'") ||
    text.includes('"phase": "final_answer"')
  );
}

/** Pull readable assistant prose from a Responses API JSON body (or pass through plain text). */
export function extractFoundryAssistantText(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed.startsWith("{")) {
    return trimmed;
  }

  try {
    const data = JSON.parse(trimmed) as {
      output?: Array<{
        type?: string;
        content?: Array<{ type?: string; text?: string }>;
      }>;
    };

    if (!Array.isArray(data.output)) {
      return trimmed;
    }

    const texts: string[] = [];
    for (const item of data.output) {
      if (item?.type !== "message" || !Array.isArray(item.content)) {
        continue;
      }
      for (const part of item.content) {
        if (part?.type === "output_text" && typeof part.text === "string") {
          const text = part.text.trim();
          if (text) {
            texts.push(text);
          }
        }
      }
    }

    if (texts.length === 0) {
      return trimmed;
    }

    const readable = texts.filter((text) => !isClassifierJson(text));
    const clean = readable.filter((text) => !isNoisyWrap(text));
    if (clean.length > 0) {
      return clean[clean.length - 1];
    }
    if (readable.length > 0) {
      return readable[readable.length - 1];
    }
    return texts[texts.length - 1];
  } catch {
    return trimmed;
  }
}

export async function invokeFoundry(
  input: string,
  accessToken?: string,
): Promise<string> {
  const url = import.meta.env.VITE_FOUNDRY_INVOKE_URL as string | undefined;
  if (!url) throw new Error("VITE_FOUNDRY_INVOKE_URL is not set");

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  let resp: Response;
  try {
    resp = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify({ input }),
    });
  } catch {
    throw new FoundryError(
      502,
      "Network error reaching the agent (is the Vite proxy target running on :8088?)",
    );
  }

  const body = await resp.text();
  if (!resp.ok) throw new FoundryError(resp.status, body);
  return body;
}

export function triageRunInput(specialistId: string): string {
  return `TRIAGE_RUN specialist_id=${specialistId}`;
}
