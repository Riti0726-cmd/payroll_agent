import { ChangeListsError, fetchChangeLists, updateChangeListStatus } from "./changelists";

describe("changelists api", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_CHANGELISTS_URL", "https://example.test/changelists");
    vi.stubEnv("VITE_QUEUE_MAILBOX", "");
    vi.stubGlobal("fetch", vi.fn());
  });

  it("GETs with specialist_id", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ items: [] }), { status: 200 }),
    );
    await fetchChangeLists("default", "tok");
    expect(fetch).toHaveBeenCalledWith(
      "https://example.test/changelists?specialist_id=default",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer tok" }),
      }),
    );
  });

  it("PATCHes approved", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({ id: "c1", clientId: "unknown", title: "DD", lines: [] }),
        { status: 200 },
      ),
    );
    await updateChangeListStatus("default", "c1", "approved", "tok");
    expect(fetch).toHaveBeenCalledWith(
      "https://example.test/changelists/c1?specialist_id=default",
      expect.objectContaining({ method: "PATCH" }),
    );
  });

  it("throws ChangeListsError on 503", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "DATABASE_URL is not set" }), { status: 503 }),
    );
    await expect(fetchChangeLists("default")).rejects.toBeInstanceOf(ChangeListsError);
  });
});
