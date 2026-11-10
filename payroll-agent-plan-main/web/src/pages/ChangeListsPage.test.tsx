import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ChangeListsPage } from "./ChangeListsPage";

vi.mock("../auth/useSpecialist", () => ({
  useSpecialist: () => ({
    displayName: "Test Specialist",
    specialistId: "specialist-1",
    getAccessToken: async () => "token-1",
    getGraphAccessToken: async () => "graph-token-1",
  }),
}));

vi.mock("../api/changelists", async () => {
  const actual = await vi.importActual<typeof import("../api/changelists")>("../api/changelists");
  return {
    ...actual,
    fetchChangeLists: vi.fn().mockResolvedValue([]),
    updateChangeListStatus: vi.fn(),
  };
});

describe("ChangeListsPage", () => {
  it("shows an empty change list workspace when API returns no items", async () => {
    vi.stubEnv("VITE_CHANGELISTS_URL", "/api/changelists");
    render(
      <MemoryRouter>
        <ChangeListsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("No change lists")).toBeInTheDocument();
    });

    expect(screen.getByRole("region", { name: "Change lists" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
  });
});
