import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { FoundryError } from "./foundry";
import { formatQaSource, invokeQaChat, QaError, sourceHasTracePanes } from "./qa";

describe("invokeQaChat", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_QA_INVOKE_URL", "https://example.test/qa");
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("POSTs full messages history with bearer token", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () =>
        JSON.stringify({
          answer: "Dental increased.",
          sources: [{ label: "structured_lines", detail: "Aug" }],
        }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const messages = [
      { role: "user" as const, content: "Why lower?" },
      { role: "assistant" as const, content: "Checking." },
      { role: "user" as const, content: "Break out deductions." },
    ];
    const result = await invokeQaChat(messages, "tok-1");
    expect(result.answer).toBe("Dental increased.");
    expect(result.sources[0].label).toBe("structured_lines");
    expect(fetchMock).toHaveBeenCalledWith(
      "https://example.test/qa",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          Authorization: "Bearer tok-1",
        }),
        body: JSON.stringify({ messages }),
      }),
    );
  });

  it("throws QaError on non-OK", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        text: async () => JSON.stringify({ detail: "boom" }),
      }),
    );
    await expect(invokeQaChat([{ role: "user", content: "x" }])).rejects.toBeInstanceOf(
      QaError,
    );
  });

  it("throws if VITE_QA_INVOKE_URL missing", async () => {
    vi.stubEnv("VITE_QA_INVOKE_URL", "");
    await expect(invokeQaChat([{ role: "user", content: "x" }])).rejects.toThrow(
      /VITE_QA_INVOKE_URL/,
    );
  });

  it("does not use FoundryError for Q&A failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        text: async () => "down",
      }),
    );
    await expect(invokeQaChat([{ role: "user", content: "x" }])).rejects.not.toBeInstanceOf(
      FoundryError,
    );
  });
  it("preserves tool-trace panes on sources", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () =>
        JSON.stringify({
          answer: "Three active employees found.",
          sources: [
            {
              label: "sv_hr_workforce",
              detail: "Returns three active employees.",
              query: "List 3 active employees",
              interpretation: "Returns three active employees.",
              response: '[{"employee_id":"E1"}]',
            },
          ],
        }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await invokeQaChat([{ role: "user", content: "list 3" }], "tok");
    expect(result.sources[0].query).toBe("List 3 active employees");
    expect(result.sources[0].interpretation).toContain("three active");
    expect(result.sources[0].response).toContain("E1");
  });
});

describe("formatQaSource", () => {
  it("joins label and detail", () => {
    expect(formatQaSource({ label: "structured", detail: "Aug" })).toBe("structured: Aug");
    expect(formatQaSource({ label: "structured" })).toBe("structured");
  });
});

describe("sourceHasTracePanes", () => {
  it("detects expandable tool sources", () => {
    expect(sourceHasTracePanes({ label: "error", detail: "x" })).toBe(false);
    expect(
      sourceHasTracePanes({
        label: "sv_hr_workforce",
        query: "q",
        interpretation: "i",
        response: "r",
      }),
    ).toBe(true);
  });
});
