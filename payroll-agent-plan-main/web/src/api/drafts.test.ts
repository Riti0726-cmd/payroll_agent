import { DraftsError, fetchDrafts, updateDraftStatus } from "./drafts";

describe("drafts api", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_DRAFTS_URL", "https://example.test/drafts");
    vi.stubEnv("VITE_QUEUE_MAILBOX", "");
    vi.stubGlobal("fetch", vi.fn());
  });

  it("GETs with specialist_id and Authorization", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ items: [] }), { status: 200 }),
    );
    await fetchDrafts("default", "tok");
    expect(fetch).toHaveBeenCalledWith(
      "https://example.test/drafts?specialist_id=default",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ Authorization: "Bearer tok" }),
      }),
    );
  });

  it("PATCHes status", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "m1",
          subject: "Hi",
          to: "a@b.com",
          body: "Edited",
          status: "accepted",
          relatedQueueId: "m1",
        }),
        { status: 200 },
      ),
    );
    await updateDraftStatus("default", "m1", "accepted", { body: "Edited", token: "tok" });
    expect(fetch).toHaveBeenCalledWith(
      "https://example.test/drafts/m1?specialist_id=default",
      expect.objectContaining({ method: "PATCH" }),
    );
  });

  it("throws DraftsError on 503", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "DATABASE_URL is not set" }), { status: 503 }),
    );
    await expect(fetchDrafts("default")).rejects.toBeInstanceOf(DraftsError);
  });
});
