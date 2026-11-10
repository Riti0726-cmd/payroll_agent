import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ThemeProvider } from "../theme/ThemeProvider";
import { AppShell } from "./AppShell";

vi.mock("../auth/useSpecialist", () => ({
  useSpecialist: () => ({
    displayName: "Test Specialist",
    specialistId: "specialist-1",
    getAccessToken: async () => "token-1",
    getGraphAccessToken: async () => "graph-token-1",
  }),
}));

const { runTriageStream } = vi.hoisted(() => ({
  runTriageStream: vi.fn(),
}));

vi.mock("../api/triage", async () => {
  const actual = await vi.importActual<typeof import("../api/triage")>("../api/triage");
  return {
    ...actual,
    runTriageStream,
  };
});

function renderShell() {
  render(
    <ThemeProvider>
      <MemoryRouter initialEntries={["/queue"]}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/queue" element={<div>Queue body</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );
}

describe("AppShell", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
    runTriageStream.mockReset();
  });

  it("runs streaming triage from the header and shows completion toast", async () => {
    vi.stubEnv("VITE_TRIAGE_STREAM_URL", "/api/triage/stream");
    runTriageStream.mockImplementation(async (_id, _token, onEvent) => {
      onEvent({ type: "run_started", runId: "r1", mailbox: "a@b.com", total: 2 });
      onEvent({
        type: "email_started",
        index: 1,
        total: 2,
        messageId: "m1",
        subject: "Pay question",
      });
      onEvent({
        type: "email_finished",
        index: 1,
        total: 2,
        messageId: "m1",
        subject: "Pay question",
        status: "succeeded",
        category: "qa",
      });
      onEvent({
        type: "run_finished",
        runId: "r1",
        succeeded: 1,
        failed: 0,
        skipped: 1,
        summary: "ok",
      });
      return {
        type: "run_finished",
        runId: "r1",
        succeeded: 1,
        failed: 0,
        skipped: 1,
        summary: "ok",
      };
    });

    renderShell();

    await userEvent.click(screen.getByRole("button", { name: "Run triage" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Triage run completed: 1 ok, 0 failed, 1 skipped",
    );
    expect(runTriageStream).toHaveBeenCalled();
  });

  it("shows a failure toast when the stream errors", async () => {
    vi.stubEnv("VITE_TRIAGE_STREAM_URL", "/api/triage/stream");
    runTriageStream.mockRejectedValue(new Error("stream down"));

    renderShell();

    await userEvent.click(screen.getByRole("button", { name: "Run triage" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Triage failed: stream down");
  });
});
