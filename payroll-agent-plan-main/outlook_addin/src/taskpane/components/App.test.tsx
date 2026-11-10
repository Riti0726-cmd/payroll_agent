import * as React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { SpecialistProvider } from "../../auth/useSpecialist";
import { ThemeProvider } from "../../theme/theme";
import { TriageRunProvider } from "../triage/TriageRunContext";
import { installOffice, makeItem } from "../../test/setup";
import type { EmailRecord } from "../../types/domain";

const record: EmailRecord = {
  id: "REST-EWS-1",
  subject: "Rate change for EMP-1",
  triaged: true,
  category: "changelist",
  priority: 3,
  receivedAt: "2026-10-01T10:00:00+05:30",
  status: "pending",
  done: false,
  clientId: "C1",
  draft: {
    id: "REST-EWS-1",
    subject: "Rate change for EMP-1",
    to: "client@example.com",
    body: "Hi,\n\n- **Rate** updated to $22",
    status: "pending",
  },
  changeList: {
    id: "REST-EWS-1",
    clientId: "C1",
    title: "Rate change",
    lines: [{ id: "l0", field: "hourly_pay_rate", from: "20", to: "22", reviewed: false }],
  },
};

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status });
}

function renderApp() {
  return render(
    <ThemeProvider>
      <SpecialistProvider>
        <TriageRunProvider>
          <App />
        </TriageRunProvider>
      </SpecialistProvider>
    </ThemeProvider>
  );
}

describe("task pane", () => {
  it("shows the open email's triage, draft and change list", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(json(200, record));
    renderApp();
    expect(await screen.findByText("Draft review")).toBeInTheDocument();
    expect(screen.getByText("Change list review")).toBeInTheDocument();
    expect(screen.getByText("Hourly pay rate")).toBeInTheDocument();
    expect(screen.getByLabelText("Priority 3")).toBeInTheDocument();
    // Draft renders as formatted markdown, not raw asterisks.
    expect(screen.getByText("Rate").tagName).toBe("STRONG");
  });

  it("offers to run triage when the email is unknown", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(json(404, { detail: "Email not found" }));
    renderApp();
    expect(await screen.findByText("The agent hasn't processed this email")).toBeInTheDocument();
  });

  it("asks to select an email when none is open", async () => {
    installOffice(null);
    renderApp();
    expect(await screen.findByText("Open an email to review")).toBeInTheDocument();
  });

  it("accepts the edited draft and inserts it into a reply", async () => {
    const item = makeItem();
    installOffice(item);
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(json(200, record))
      .mockResolvedValueOnce(json(200, { ...record.draft, status: "accepted", body: "Hi there" }));
    const user = userEvent.setup();
    renderApp();

    await user.click(await screen.findByRole("button", { name: "Edit" }));
    const box = screen.getByLabelText("Draft response body");
    await user.clear(box);
    await user.type(box, "Hi there");
    await user.click(screen.getByRole("button", { name: "Accept" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const [url, init] = fetchMock.mock.calls[1];
    expect(String(url)).toContain("/api/drafts/REST-EWS-1");
    expect(JSON.parse(String(init?.body))).toEqual({ status: "accepted", body: "Hi there" });

    await user.click(await screen.findByRole("button", { name: /Insert into reply/ }));
    expect(item.displayReplyForm).toHaveBeenCalledWith({ htmlBody: "<p>Hi there</p>" });
  });
});
