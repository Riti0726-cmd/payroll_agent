import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { fetchQueue, QueueError } from "./queue";

describe("fetchQueue", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_QUEUE_URL", "https://example.test/queue");
    vi.stubEnv("VITE_QUEUE_MAILBOX", "");
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("GETs with specialist_id and Authorization", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ items: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchQueue("default", "tok");
    expect(fetchMock).toHaveBeenCalledWith(
      "https://example.test/queue?specialist_id=default",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ Authorization: "Bearer tok" }),
      }),
    );
  });

  it("appends mailbox when VITE_QUEUE_MAILBOX is set", async () => {
    vi.stubEnv("VITE_QUEUE_MAILBOX", "payroll@peoservices.com");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ items: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchQueue("default");
    expect(fetchMock).toHaveBeenCalledWith(
      "https://example.test/queue?specialist_id=default&mailbox=payroll%40peoservices.com",
      expect.anything(),
    );
  });

  it("throws QueueError on 503", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        text: async () => JSON.stringify({ detail: "DATABASE_URL is not set" }),
      }),
    );
    await expect(fetchQueue("default")).rejects.toBeInstanceOf(QueueError);
  });

  it("throws if VITE_QUEUE_URL missing", async () => {
    vi.stubEnv("VITE_QUEUE_URL", "");
    await expect(fetchQueue("default")).rejects.toThrow(/VITE_QUEUE_URL/);
  });
});
