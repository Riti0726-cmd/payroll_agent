import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { invokeFoundry, FoundryError, extractFoundryAssistantText } from "./foundry";

describe("invokeFoundry", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_FOUNDRY_INVOKE_URL", "https://example.test/invoke");
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("POSTs { input } with bearer token", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => "hello",
    });
    vi.stubGlobal("fetch", fetchMock);

    const text = await invokeFoundry("Why was pay lower?", "tok-1");
    expect(text).toBe("hello");
    expect(fetchMock).toHaveBeenCalledWith(
      "https://example.test/invoke",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          Authorization: "Bearer tok-1",
        }),
        body: JSON.stringify({ input: "Why was pay lower?" }),
      }),
    );
  });

  it("throws FoundryError on non-OK", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        text: async () => "boom",
      }),
    );
    await expect(invokeFoundry("x")).rejects.toBeInstanceOf(FoundryError);
  });

  it("throws if VITE_FOUNDRY_INVOKE_URL missing", async () => {
    vi.stubEnv("VITE_FOUNDRY_INVOKE_URL", "");
    await expect(invokeFoundry("x")).rejects.toThrow(/VITE_FOUNDRY_INVOKE_URL/);
  });
});

describe("extractFoundryAssistantText", () => {
  it("returns plain text unchanged", () => {
    expect(extractFoundryAssistantText("hello")).toBe("hello");
  });

  it("extracts readable assistant prose from Responses JSON", () => {
    const raw = JSON.stringify({
      object: "response",
      output: [
        {
          type: "message",
          content: [
            {
              type: "output_text",
              text: '{"category":"out_of_scope","intent":"greeting","confidence":0.99}',
            },
          ],
        },
        {
          type: "message",
          content: [
            {
              type: "output_text",
              text: "Route to **General HR / Other**.\n\nThe inquiry only contains a greeting.",
            },
          ],
        },
        {
          type: "message",
          content: [
            {
              type: "output_text",
              text: "**Triaged Category:** OUT_OF_SCOPE\n\n[{'type': 'text', 'text': 'Route to...', 'phase': 'final_answer'}]",
            },
          ],
        },
      ],
    });

    expect(extractFoundryAssistantText(raw)).toBe(
      "Route to **General HR / Other**.\n\nThe inquiry only contains a greeting.",
    );
  });
});
