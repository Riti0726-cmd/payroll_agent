import { describe, expect, it } from "vitest";
import { installOffice, makeItem } from "../test/setup";
import {
  getBodyText,
  getCurrentItem,
  isOfficeDarkTheme,
  openMessage,
  openReplyWithDraft,
} from "./mailbox";

describe("office mailbox wrappers", () => {
  it("converts the EWS item id to a REST id", () => {
    const { mailbox } = installOffice();
    expect(getCurrentItem()).toEqual({
      restId: "REST-EWS-1",
      internetMessageId: "<abc@example.com>",
      subject: "Rate change for EMP-1",
      from: "client@example.com",
    });
    expect(mailbox.convertToRestId).toHaveBeenCalledWith("EWS-1", "v2.0");
  });

  it("returns null when no message is selected", () => {
    installOffice(null);
    expect(getCurrentItem()).toBeNull();
  });

  it("reads the body as text", async () => {
    installOffice();
    await expect(getBodyText()).resolves.toBe("Please update EMP-1 to $22/hr.");
  });

  it("opens a prefilled reply without sending", () => {
    const item = makeItem();
    installOffice(item);
    openReplyWithDraft("<p>Hi</p>");
    expect(item.displayReplyForm).toHaveBeenCalledWith({ htmlBody: "<p>Hi</p>" });
  });

  it("opens a queue message by REST id", () => {
    const { mailbox } = installOffice();
    openMessage("AAMk");
    expect(mailbox.displayMessageForm).toHaveBeenCalledWith("EWS-AAMk");
  });

  it("detects a dark Outlook theme", () => {
    const { office } = installOffice();
    expect(isOfficeDarkTheme()).toBe(false);
    office.context.officeTheme.bodyBackgroundColor = "#1f1f1f";
    expect(isOfficeDarkTheme()).toBe(true);
  });
});
