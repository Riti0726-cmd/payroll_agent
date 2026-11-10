import * as React from "react";
import { patchQueueItem } from "../../api/workbench";
import { useSpecialist } from "../../auth/useSpecialist";
import type { CurrentItem } from "../../office/mailbox";
import type { EmailRecord, Priority } from "../../types/domain";
import { useEmailRecord } from "../hooks/useEmailRecord";
import { useTriageRun } from "../triage/TriageRunContext";
import { ChangeListReview } from "./ChangeListReview";
import { DraftReview } from "./DraftReview";
import styles from "./EmailTab.module.css";
import { formatDate, humanizeField } from "./format";
import { CategoryChip, PriorityBadge, StatusBadge, formatStatus } from "./ui/Badges";
import { EmptyState, ErrorBox, InlineNote, MetaGrid, Toast } from "./ui/Feedback";

const PRIORITIES: Priority[] = [1, 2, 3, 4, 5];

/** Triage summary — the web Queue page detail (eyebrow, badges, meta tiles, priority adjust). */
function TriageSummary({
  record,
  onChange,
  notify,
}: {
  record: EmailRecord;
  onChange: (patch: Partial<EmailRecord>) => void;
  notify: (message: string) => void;
}) {
  const { user, getAccessToken } = useSpecialist();
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const extracted = record.extracted ?? {};

  const save = async (patch: { priority?: Priority; done?: boolean }) => {
    if (!user) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await patchQueueItem(user.specialistId, record.id, patch, await getAccessToken());
      onChange({ priority: updated.priority, ...(patch.done ? { done: true, status: "done" } : {}) });
      notify(patch.done ? "Marked done — removed from your queue" : `Priority set to P${updated.priority}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <article className={styles.panel} data-enter>
      <header className={styles.panelHeader}>
        <div>
          <span className={styles.eyebrow}>Triage result</span>
          <h2>{record.subject}</h2>
        </div>
      </header>
      <div className={styles.panelBody}>
        <div className={styles.badges}>
          <PriorityBadge priority={record.priority} />
          {record.category ? <CategoryChip category={record.category} /> : null}
          {record.done ? (
            <StatusBadge tone="ok">Done</StatusBadge>
          ) : record.status ? (
            <StatusBadge tone={record.status === "needs_clarification" ? "warn" : "neutral"}>
              {formatStatus(record.status)}
            </StatusBadge>
          ) : null}
        </div>
        <MetaGrid
          items={[
            { label: "Client", value: record.clientId ?? extracted.client_id },
            { label: "Employee", value: record.employeeId ?? extracted.employee_id },
            { label: "Name", value: extracted.employee_name },
            { label: "Change", value: extracted.change_type ? humanizeField(extracted.change_type) : undefined },
            { label: "Effective", value: extracted.effective_date ? formatDate(extracted.effective_date) : undefined },
            { label: "Pay period", value: extracted.pay_period },
          ]}
        />
        <ErrorBox label="Update failed" message={error} />
      </div>
      <div className={styles.actions}>
        <label className={styles.priorityAdjust}>
          <span>Priority</span>
          <select
            aria-label="Priority"
            disabled={busy || record.done}
            value={record.priority}
            onChange={(event) => {
              const next = Number(event.target.value) as Priority;
              if (next !== record.priority) void save({ priority: next });
            }}
          >
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                P{p}
              </option>
            ))}
          </select>
        </label>
        {!record.done ? (
          <button className={styles.actionsEnd} type="button" disabled={busy} onClick={() => void save({ done: true })}>
            Mark done
          </button>
        ) : null}
      </div>
    </article>
  );
}

export function EmailTab({ item }: { item: CurrentItem | null }) {
  const { record, loading, error, reload, update } = useEmailRecord(item);
  const triage = useTriageRun();
  const [toast, setToast] = React.useState<string | null>(null);
  const dismissToast = React.useCallback(() => setToast(null), []);

  // Pick up new results after a triage run started from any tab.
  const lastRun = React.useRef(triage.runCount);
  React.useEffect(() => {
    if (triage.runCount !== lastRun.current) {
      lastRun.current = triage.runCount;
      reload();
    }
  }, [triage.runCount, reload]);

  if (!item) {
    return (
      <EmptyState
        kicker="No email selected"
        title="Open an email to review"
        detail="Select a message in your inbox to see the agent's triage, draft reply and change list."
      />
    );
  }

  if (loading && !record) {
    return <InlineNote kicker="Loading">Fetching the agent's triage for this email…</InlineNote>;
  }

  if (error) {
    return <ErrorBox label="Unable to load triage" message={error} onRetry={reload} />;
  }

  if (!record || !record.triaged) {
    return (
      <EmptyState
        kicker="Not triaged"
        title="The agent hasn't processed this email"
        detail="Run triage to classify new mail in your mailbox. Results appear here when it finishes."
      >
        <button
          className="btn-primary"
          type="button"
          disabled={triage.isRunning}
          onClick={() => void triage.startTriage()}
        >
          {triage.isRunning ? "Running triage…" : "Run triage"}
        </button>
      </EmptyState>
    );
  }

  return (
    <>
      <TriageSummary record={record} onChange={update} notify={setToast} />
      {record.draft ? (
        <DraftReview
          draft={record.draft}
          onChange={(draft) => update({ draft, status: draft.status })}
          notify={setToast}
        />
      ) : null}
      {record.changeList ? (
        <ChangeListReview
          changeList={record.changeList}
          reviewStatus={record.status}
          onChange={(changeList, status) => update({ changeList, status })}
          notify={setToast}
        />
      ) : null}
      <Toast message={toast} onDismiss={dismissToast} />
    </>
  );
}
