import { fetchSettings, saveSettings, SettingsError } from "./settings";

describe("settings api", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_SETTINGS_URL", "https://example.test/settings");
    vi.stubGlobal("fetch", vi.fn());
  });

  it("GETs with specialist_id", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          lookbackDays: 7,
          mode: "manual",
          intervalHours: 2,
          runs: [],
        }),
        { status: 200 },
      ),
    );
    await fetchSettings("default", "tok");
    expect(fetch).toHaveBeenCalledWith(
      "https://example.test/settings?specialist_id=default",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer tok" }),
      }),
    );
  });

  it("PUTs body", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          lookbackDays: 14,
          mode: "recurring",
          intervalHours: 4,
          runs: [],
        }),
        { status: 200 },
      ),
    );
    await saveSettings("default", {
      lookbackDays: 14,
      mode: "recurring",
      intervalHours: 4,
    });
    expect(fetch).toHaveBeenCalledWith(
      "https://example.test/settings?specialist_id=default",
      expect.objectContaining({ method: "PUT" }),
    );
  });

  it("throws SettingsError on failure", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "bad" }), { status: 400 }),
    );
    await expect(fetchSettings("default")).rejects.toBeInstanceOf(SettingsError);
  });
});
