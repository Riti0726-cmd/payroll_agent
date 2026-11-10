import * as React from "react";
import { updateDraftStatus } from "../../api/workbench";
import { useSpecialist } from "../../auth/useSpecialist";
import { markdownToHtml } from "../../lib/markdown";
import { openReplyWithDraft } from "../../office/mailbox";
import type { DraftItem } from "../../types/domain";
import styles from "./EmailTab.module.css";
import { StatusBadge, formatStatus } from "./ui/Badges";
import { ErrorBox } from "./ui/Feedback";
import { MarkdownBody } from "./ui/MarkdownBody";

/** Draft review card — mirrors web DraftsPage detail (preview ⇄ edit, HITL actions). */
export function DraftReview({
  draft,
  onChange,
  notify,
}: {
  draft: DraftItem;
  onChange: (draft: DraftItem) => void;
  notify: (message: string) => void;
}) {
  const { user, getAccessToken } = useSpecialist();
  const [isEditing, setIsEditing] = React.useState(false);
  const [body, setBody] = React.useState(draft.body);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    setBody(draft.body);
    setIsEditing(false);
  }, [draft.id, draft.body]);

  const pending = draft.status === "pending";
  const discarded = draft.status === "discarded";

  const setStatus = async (status: "accepted" | "discarded") => {
    if (!user) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await updateDraftStatus(user.specialistId, draft.id, status, {
        body: status === "accepted" ? body : undefined,
        token: await getAccessToken(),
      });
      setIsEditing(false);
      onChange(updated);
      notify(status === "accepted" ? "Draft accepted" : "Draft discarded");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const insertIntoReply = () => {
    setError(null);
    try {
      openReplyWithDraft(markdownToHtml(body));
      notify("Reply opened — review and press Send in Outlook");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <article className={styles.panel} data-enter style={{ "--enter-index": 1 } as React.CSSProperties}>
      <header className={styles.panelHeader}>
        <div>
          <span className={styles.eyebrow}>Draft review</span>
          <h3>Reply to {draft.to || "sender"}</h3>
        </div>
        <StatusBadge tone={pending ? "warn" : draft.status === "accepted" ? "ok" : "neutral"}>
          {formatStatus(draft.status)}
        </StatusBadge>
      </header>

      <div className={styles.panelBody}>
        {isEditing ? (
          <label className={styles.editor}>
            <span className={styles.fieldLabel}>Response body</span>
            <textarea
              aria-label="Draft response body"
              rows={12}
              value={body}
              disabled={busy}
              onChange={(event) => setBody(event.target.value)}
            />
            <span className={styles.hint}>
              Markdown: blank line for a new paragraph, “- ” for bullets, **bold**.
            </span>
          </label>
        ) : (
          <div className={styles.editor}>
            <span className={styles.fieldLabel}>Response body</span>
            <MarkdownBody source={body} emptyLabel="No draft body has been generated yet." />
          </div>
        )}
        <ErrorBox label="Draft action failed" message={error} />
      </div>

      <div className={styles.actions}>
        {pending ? (
          <button className="btn-primary" type="button" disabled={busy} onClick={() => void setStatus("accepted")}>
            Accept
          </button>
        ) : null}
        {!discarded ? (
          <button
            className={pending ? undefined : "btn-primary"}
            type="button"
            disabled={busy || !body.trim()}
            title="Opens an Outlook reply with this text. Nothing is sent until you press Send."
            onClick={insertIntoReply}
          >
            Insert into reply
          </button>
        ) : null}
        {pending ? (
          <button type="button" disabled={busy} onClick={() => setIsEditing((v) => !v)}>
            {isEditing ? "Preview" : "Edit"}
          </button>
        ) : null}
        {pending ? (
          <button
            className={styles.actionsEnd}
            type="button"
            disabled={busy}
            onClick={() => void setStatus("discarded")}
          >
            Discard
          </button>
        ) : null}
      </div>
    </article>
  );
}
