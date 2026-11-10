import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TriageRunProvider } from "../triage/TriageRunContext";
import { SettingsPage } from "./SettingsPage";

const { signOut } = vi.hoisted(() => ({
  signOut: vi.fn().mockResolvedValue(undefined),
}));

const { runTriageStream } = vi.hoisted(() => ({
  runTriageStream: vi.fn(),
}));

vi.mock("../auth/useSpecialist", () => ({
  useSpecialist: () => ({
    displayName: "Test Specialist",
    specialistId: "specialist-1",
    getAccessToken: async () => "token-1",
    getGraphAccessToken: async () => "graph-token-1",
    signOut,
  }),
}));

vi.mock("../api/triage", async () => {
  const actual = await vi.importActual<typeof import("../api/triage")>("../api/triage");
  return {
    ...actual,
    runTriageStream,
  };
});

vi.mock("../api/settings", async () => {
  const actual = await vi.importActual<typeof import("../api/settings")>("../api/settings");
  return {
    ...actual,
    fetchSettings: vi.fn().mockResolvedValue({
      lookbackDays: 7,
      mode: "manual",
      intervalHours: 2,
      runs: [],
    }),
    saveSettings: vi.fn().mockResolvedValue({
      lookbackDays: 14,
      mode: "recurring",
      intervalHours: 4,
      runs: [],
    }),
  };
});

function renderSettings() {
  return render(
    <TriageRunProvider>
      <SettingsPage />
    </TriageRunProvider>,
  );
}

describe("SettingsPage", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
    signOut.mockClear();
    runTriageStream.mockReset();
  });

  it("loads settings and runs triage stream", async () => {
    vi.stubEnv("VITE_SETTINGS_URL", "/api/settings");
    vi.stubEnv("VITE_TRIAGE_STREAM_URL", "/api/triage/stream");
    runTriageStream.mockImplementation(async (_id, _token, onEvent) => {
      onEvent({
        type: "run_finished",
        runId: "r1",
        succeeded: 2,
        failed: 0,
        skipped: 0,
        summary: "done",
      });
      return {
        type: "run_finished",
        runId: "r1",
        succeeded: 2,
        failed: 0,
        skipped: 0,
        summary: "done",
      };
    });

    renderSettings();

    await waitFor(() => {
      expect(screen.getByLabelText("Lookback days")).toHaveValue(7);
    });

    expect(screen.getByRole("button", { name: "Save configuration" })).toBeInTheDocument();
    expect(screen.getByText("No run history yet")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Run triage" }));

    await waitFor(() => {
      expect(runTriageStream).toHaveBeenCalled();
    });
  });

  it("shows account details and signs out", async () => {
    vi.stubEnv("VITE_SETTINGS_URL", "/api/settings");

    renderSettings();

    expect(await screen.findByText("Test Specialist")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(signOut).toHaveBeenCalledTimes(1);
  });
});
