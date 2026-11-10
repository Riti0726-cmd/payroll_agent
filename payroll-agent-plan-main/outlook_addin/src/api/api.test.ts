import { describe, expect, it, vi } from "vitest";
import { parseSseFrames } from "./sse";
import { askQa } from "./streams";
import { lookupEmail, patchQueueItem } from "./workbench";

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("lookupEmail", () => {
  it("sends both ids and the bearer token", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse(200, { id: "REST-1", triaged: true, priority: 3 }));
    const record = await lookupEmail(
      "s@x.com",
      { restId: "REST-1", internetMessageId: "<a@b>" },
      "tok"
    );
    expect(record?.id).toBe("REST-1");
    const [url, init] = fetchMock.mock.calls[0];
    const parsed = new URL(String(url));
    expect(parsed.pathname).toBe("/api/emails/lookup");
    expect(parsed.searchParams.get("specialist_id")).toBe("s@x.com");
    expect(parsed.searchParams.get("rest_id")).toBe("REST-1");
    expect(parsed.searchParams.get("internet_message_id")).toBe("<a@b>");
    expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer tok");
  });

  it("returns null on 404 (email not ingested yet)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(404, { detail: "Email not found" })
    );
    expect(await lookupEmail("s", { restId: "x" })).toBeNull();
  });

  it("surfaces backend detail on other errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(503, { detail: "DATABASE_URL missing" })
    );
    await expect(lookupEmail("s", { restId: "x" })).rejects.toThrow("DATABASE_URL missing");
  });
});

describe("patchQueueItem", () => {
  it("PATCHes priority as JSON", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse(200, { id: "a", priority: 1 }));
    await patchQueueItem("s", "id/1", { priority: 1 });
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/api/queue/id%2F1?");
    expect(init?.method).toBe("PATCH");
    expect(init?.body).toBe('{"priority":1}');
  });
});

describe("parseSseFrames", () => {
  it("parses complete frames and keeps the partial remainder", () => {
    const seen: string[] = [];
    const rest = parseSseFrames(
      'event: tool_started\ndata: {"name":"cortex"}\n\nevent: finished\ndata: {"answer":"4"',
      (type) => seen.push(type)
    );
    expect(seen).toEqual(["tool_started"]);
    expect(rest).toContain("finished");
  });
});

describe("askQa", () => {
  it("streams progress and resolves with the answer", async () => {
    const sse =
      "event: started\ndata: {}\n\n" +
      'event: tool_started\ndata: {"name":"cortex","label":"Querying payroll"}\n\n' +
      'event: finished\ndata: {"answer":"Net pay was $1,200.","sources":[{"label":"Cortex"}]}\n\n';
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(sse, { status: 200 }));
    const events: string[] = [];
    const result = await askQa([{ role: "user", content: "q" }], undefined, (e) =>
      events.push(e.type)
    );
    expect(events).toEqual(["started", "tool_started", "finished"]);
    expect(result).toEqual({
      answer: "Net pay was $1,200.",
      sources: [expect.objectContaining({ label: "Cortex" })],
    });
  });

  it("rejects on a stream error event", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response('event: error\ndata: {"message":"MCP down"}\n\n', { status: 200 })
    );
    await expect(
      askQa([{ role: "user", content: "q" }], undefined, () => undefined)
    ).rejects.toThrow("MCP down");
  });
});
