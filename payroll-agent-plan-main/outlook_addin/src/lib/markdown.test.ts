import { describe, expect, it } from "vitest";
import { markdownToHtml, stripDraftMeta } from "./markdown";

describe("markdownToHtml", () => {
  it("renders paragraphs, bullets and bold", () => {
    const html = markdownToHtml(
      "Hi Sam,\n\nWe updated:\n- **Rate** to $22\n- Effective 10/1\n\nThanks"
    );
    expect(html).toBe(
      "<p>Hi Sam,</p><p>We updated:</p><ul><li><strong>Rate</strong> to $22</li><li>Effective 10/1</li></ul><p>Thanks</p>"
    );
  });

  it("escapes HTML so email content cannot inject markup", () => {
    expect(markdownToHtml('<img src=x onerror="alert(1)">')).toBe(
      "<p>&lt;img src=x onerror=&quot;alert(1)&quot;&gt;</p>"
    );
  });

  it("strips the drafter's triage header", () => {
    const md = "**Triaged Category:** qa\n**Employee ID:** EMP-1\n\nHello";
    expect(stripDraftMeta(md)).toBe("Hello");
    expect(markdownToHtml(md)).toBe("<p>Hello</p>");
  });
});
