/** Shared Neon mailbox override for Queue / Drafts / Change lists. */
export function appendMailboxParam(url: URL): void {
  const mailbox = (import.meta.env.VITE_QUEUE_MAILBOX as string | undefined)?.trim();
  if (mailbox) {
    url.searchParams.set("mailbox", mailbox);
  }
}
