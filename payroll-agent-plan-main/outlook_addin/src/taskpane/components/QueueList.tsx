// Queue tab — web QueuePage toolbar + list rows, opening the email in Outlook on click.
import * as React from "react";
import { fetchQueue } from "../../api/workbench";
import { useSpecialist } from "../../auth/useSpecialist";
import { sortQueueItems } from "../../lib/queueSort";
import { openMessage } from "../../office/mailbox";
import type { QueueItem } from "../../types/domain";
import { useTriageRun } from "../triage/TriageRunContext";
import { formatReceived } from "./format";
import styles from "./QueueList.module.css";
import { CategoryChip, PriorityBadge } from "./ui/Badges";
import { ErrorBox, InlineNote } from "./ui/Feedback";

export function QueueList() {
  const { user, getAccessToken } = useSpecialist();
  const triage = useTriageRun();
  const [items, setItems] = React.useState<QueueItem[] | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const specialistId = user?.specialistId;

  const load = React.useCallback(async () => {
    if (!specialistId) return;
    setLoading(true);
    setError(null);
    try {
      setItems(sortQueueItems(await fetchQueue(specialistId, await getAccessToken())));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
    // getAccessToken identity follows auth state, which specialistId already tracks.
  }, [specialistId]);

  React.useEffect(() => {
    void load();
  }, [load, triage.runCount]);

  const open = (id: string) => {
    try {
      openMessage(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const urgent = items?.filter((item) => item.priority <= 2).length ?? 0;

  return (
    <>
      <section className={styles.toolbar} data-enter>
        <div>
          <span className={styles.eyebrow}>Open queue</span>
          <h2>{items ? `${items.length} awaiting review` : "Your queue"}</h2>
          {urgent > 0 ? <span className={styles.toolbarNote}>{urgent} high priority</span> : null}
        </div>
        <div className={styles.toolbarActions}>
          <button type="button" disabled={loading} onClick={() => void load()} aria-label="Refresh queue">
            Refresh
          </button>
          <button
            className="btn-primary"
            type="button"
            disabled={triage.isRunning}
            onClick={() => void triage.startTriage()}
          >
            {triage.isRunning ? "Running…" : "Run triage"}
          </button>
        </div>
      </section>

      <section className={styles.list} aria-label="Queue items" data-enter style={{ "--enter-index": 1 } as React.CSSProperties}>
        <div className={styles.listLabel}>Sorted by priority, then oldest first</div>
        {error ? <ErrorBox label="Unable to load queue" message={error} onRetry={() => void load()} /> : null}
        {loading && !items ? <InlineNote kicker="Loading">Fetching your open queue…</InlineNote> : null}
        {items && items.length === 0 ? (
          <InlineNote kicker="Queue clear">Nothing waiting. Run triage to pull in new mail.</InlineNote>
        ) : null}
        {items?.map((item) => (
          <button key={item.id} type="button" className={styles.row} onClick={() => open(item.id)}>
            <span className={styles.rowMeta}>
              <PriorityBadge priority={item.priority} />
              <CategoryChip category={item.category} />
              <span className={styles.timestamp}>{formatReceived(item.receivedAt)}</span>
            </span>
            <span className={styles.subject}>{item.subject}</span>
            <span className={styles.rowFooter}>
              <span>{item.clientId ? `Client ${item.clientId}` : "No client"}</span>
              {item.hasDraft ? <span className={styles.draftReady}>Draft ready</span> : null}
            </span>
          </button>
        ))}
      </section>
    </>
  );
}
