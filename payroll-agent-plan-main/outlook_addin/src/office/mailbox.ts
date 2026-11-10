// Thin wrappers over Office.js mailbox APIs (read mode, Mailbox 1.5+).

export interface CurrentItem {
  /** Graph REST id (v2.0), matches email_processing.message_id */
  restId: string;
  internetMessageId: string;
  subject: string;
  from: string;
}

function readItem(): Office.MessageRead | null {
  const item = Office.context.mailbox?.item as Office.MessageRead | null | undefined;
  // Compare the string value ("message") so this never throws before MailboxEnums loads.
  if (!item || String(item.itemType) !== "message" || !item.itemId) {
    return null;
  }
  return item;
}

/** The message open in the reading pane, or null (nothing selected / compose / meeting). */
export function getCurrentItem(): CurrentItem | null {
  const item = readItem();
  if (!item) return null;
  const mailbox = Office.context.mailbox;
  return {
    restId: mailbox.convertToRestId(item.itemId, Office.MailboxEnums.RestVersion.v2_0),
    internetMessageId: item.internetMessageId ?? "",
    subject: item.subject ?? "",
    from: item.from?.emailAddress ?? "",
  };
}

export function getBodyText(): Promise<string> {
  const item = readItem();
  if (!item) return Promise.resolve("");
  return new Promise((resolve, reject) => {
    item.body.getAsync(Office.CoercionType.Text, (result) => {
      if (result.status === Office.AsyncResultStatus.Succeeded) resolve(result.value ?? "");
      else reject(new Error(result.error?.message ?? "Could not read the email body"));
    });
  });
}

/** Open a reply form prefilled with html. Outlook never sends it; the specialist does. */
export function openReplyWithDraft(htmlBody: string): void {
  const item = readItem();
  if (!item) throw new Error("Open an email to reply to.");
  item.displayReplyForm({ htmlBody });
}

/** Open another message (e.g. from the queue) given its Graph REST id. */
export function openMessage(restId: string): void {
  const mailbox = Office.context.mailbox;
  mailbox.displayMessageForm(mailbox.convertToEwsId(restId, Office.MailboxEnums.RestVersion.v2_0));
}

/** Fires when the selected email changes while the pane is pinned. Returns an unsubscribe fn. */
export function onItemChanged(handler: () => void): () => void {
  const mailbox = Office.context.mailbox;
  if (!mailbox?.addHandlerAsync) return () => undefined;
  mailbox.addHandlerAsync(Office.EventType.ItemChanged, handler);
  return () => {
    mailbox.removeHandlerAsync(Office.EventType.ItemChanged);
  };
}

/** Outlook light/dark: true when the host body background is dark. */
export function isOfficeDarkTheme(): boolean {
  const bg = Office.context.officeTheme?.bodyBackgroundColor;
  if (!bg || !/^#?[0-9a-f]{6}$/i.test(bg)) return false;
  const hex = bg.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b < 128;
}
