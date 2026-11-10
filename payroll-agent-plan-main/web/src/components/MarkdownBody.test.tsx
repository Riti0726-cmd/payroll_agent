import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MarkdownBody } from "./MarkdownBody";

describe("MarkdownBody", () => {
  it("renders triage meta and bold text without raw markers", () => {
    render(
      <MarkdownBody
        source={
          "**Triaged Category:** QA\n**Employee ID:** A04801\n\nHello **world**,\n\n- **Field:** Direct deposit"
        }
      />,
    );

    expect(screen.getByText("Category")).toBeInTheDocument();
    expect(screen.getByText("QA")).toBeInTheDocument();
    expect(screen.getByText("A04801")).toBeInTheDocument();
    expect(screen.getByText("world")).toBeInTheDocument();
    expect(screen.queryByText(/\*\*Triaged Category:\*\*/)).not.toBeInTheDocument();
    expect(screen.getByText(/Field:/)).toBeInTheDocument();
  });
});
