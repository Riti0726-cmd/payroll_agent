// POST + fetch-stream SSE reader (native EventSource cannot POST).
// Frame format matches the backend: "event: <type>\ndata: <json>\n\n".

/** Parse complete SSE frames from buffer; returns the leftover partial frame. */
export function parseSseFrames(
  buffer: string,
  onFrame: (type: string, payload: Record<string, unknown>) => void
): string {
  const parts = buffer.replace(/\r\n/g, "\n").split("\n\n");
  const rest = parts.pop() ?? "";
  for (const part of parts) {
    if (!part.trim()) continue;
    let eventType = "message";
    const dataLines: string[] = [];
    for (const line of part.split("\n")) {
      if (line.startsWith("event:")) eventType = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }
    if (dataLines.length === 0) continue;
    try {
      const payload = JSON.parse(dataLines.join("\n")) as Record<string, unknown>;
      onFrame(typeof payload.type === "string" ? payload.type : eventType, payload);
    } catch {
      /* ignore malformed frames */
    }
  }
  return rest;
}

export async function readSseStream(
  resp: Response,
  onFrame: (type: string, payload: Record<string, unknown>) => void
): Promise<void> {
  if (!resp.body) throw new Error("Stream returned an empty body");
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    buffer = parseSseFrames(buffer, onFrame);
  }
  if (buffer.trim()) parseSseFrames(`${buffer}\n\n`, onFrame);
}
