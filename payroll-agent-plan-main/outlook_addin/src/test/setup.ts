import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

export interface MockItem {
  itemId: string;
  itemType: string;
  internetMessageId: string;
  subject: string;
  from: { emailAddress: string };
  body: { getAsync: ReturnType<typeof vi.fn> };
  displayReplyForm: ReturnType<typeof vi.fn>;
}

export function makeItem(overrides: Partial<MockItem> = {}): MockItem {
  return {
    itemId: "EWS-1",
    itemType: "message",
    internetMessageId: "<abc@example.com>",
    subject: "Rate change for EMP-1",
    from: { emailAddress: "client@example.com" },
    body: {
      getAsync: vi.fn((_type: unknown, cb: (r: unknown) => void) =>
        cb({ status: "succeeded", value: "Please update EMP-1 to $22/hr." })
      ),
    },
    displayReplyForm: vi.fn(),
    ...overrides,
  };
}

/** Minimal Office.js global for read-mode mail tests. */
export function installOffice(item: MockItem | null = makeItem()) {
  const mailbox = {
    item,
    convertToRestId: vi.fn((id: string) => `REST-${id}`),
    convertToEwsId: vi.fn((id: string) => `EWS-${id}`),
    displayMessageForm: vi.fn(),
    addHandlerAsync: vi.fn(),
    removeHandlerAsync: vi.fn(),
  };
  const office = {
    context: {
      mailbox,
      officeTheme: { bodyBackgroundColor: "#ffffff" },
      requirements: { isSetSupported: vi.fn(() => false) },
      ui: { displayDialogAsync: vi.fn(), messageParent: vi.fn() },
    },
    MailboxEnums: { ItemType: { Message: "message" }, RestVersion: { v2_0: "v2.0" } },
    CoercionType: { Text: "text" },
    AsyncResultStatus: { Succeeded: "succeeded", Failed: "failed" },
    EventType: {
      ItemChanged: "olkItemSelectedChanged",
      DialogMessageReceived: "dialogMessageReceived",
      DialogEventReceived: "dialogEventReceived",
    },
    onReady: vi.fn(),
  };
  (globalThis as unknown as { Office: unknown }).Office = office;
  return { office, mailbox };
}

installOffice();

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  installOffice();
});
