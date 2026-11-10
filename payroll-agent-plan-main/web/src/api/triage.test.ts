import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { runTriage, runTriageStream } from "./triage";

describe("runTriage", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_FOUNDRY_INVOKE_URL", "https://example.test/invoke");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("invokes Foundry with the specialist triage command", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => "queued",
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await runTriage("specialist-1", "token-1");

    expect(result).toBe("queued");
    expect(fetchMock).toHaveBeenCalledWith(
      "https://example.test/invoke",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          Authorization: "Bearer token-1",
        }),
        body: JSON.stringify({ input: "TRIAGE_RUN specialist_id=specialist-1" }),
      }),
    );
  });
});

describe("runTriageStream", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("parses SSE progress events", async () => {
    vi.stubEnv("VITE_TRIAGE_STREAM_URL", "/api/triage/stream");
    const payload =
      'event: run_started\ndata: {"type":"run_started","runId":"r1","mailbox":"a@b.com","total":1}\n\n' +
      'event: run_finished\ndata: {"type":"run_finished","runId":"r1","succeeded":1,"failed":0,"skipped":0,"summary":"ok"}\n\n';
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(payload));
        controller.close();
      },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        body: stream,
      }),
    );

    const events: Array<{ type: string }> = [];
    const last = await runTriageStream("specialist-1", "tok", (e) => events.push(e));
    expect(events.map((e) => e.type)).toEqual(["run_started", "run_finished"]);
    expect(last?.type).toBe("run_finished");
  });
});
