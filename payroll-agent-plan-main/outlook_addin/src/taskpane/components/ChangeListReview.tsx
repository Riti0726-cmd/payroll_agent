import * as React from "react";
import { patchChangeList } from "../../api/workbench";
import { useSpecialist } from "../../auth/useSpecialist";
import type { ChangeListItem } from "../../types/domain";
import styles from "./EmailTab.module.css";
import { PriorityBadge, StatusBadge, formatStatus } from "./ui/Badges";
import { ErrorBox, MetaGrid } from "./ui/Feedback";
import { formatDate, humanizeField } from "./format";

/** hitl_status values that mean the reviewer already decided. */
const DECIDED = new Set(["approved", "needs_clarification", "done"]);

/** Change list review card — mirrors web ChangeListsPage detail (read-only lines). */
export function ChangeListReview({
  changeList,
  reviewStatus,
  onChange,
  notify,
}: {
  changeList: ChangeListItem;
  reviewStatus?: string;
  onChange: (changeList: ChangeListItem, status: string) => void;
  notify: (message: string) => void;
}) {
  const { user, getAccessToken } = useSpecialist();
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const decided = reviewStatus ? DECIDED.has(reviewStatus) : false;
  const incompleteCount = changeList.lines.filter((line) => line.incomplete).length;

  const decide = async (status: "approved" | "needs_clarification") => {
    if (!user) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await patchChangeList(
        user.specialistId,
        changeList.id,
        { status },
        await getAccessToken()
      );
      onChange(updated, status);
      notify(status === "approved" ? "Change list approved" : "Marked as needs clarification");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const headerStatus = decided ? reviewStatus : incompleteCount > 0 ? "incomplete" : changeList.status;

  return (
    <article className={styles.panel} data-enter style={{ "--enter-index": 2 } as React.CSSProperties}>
      <header className={styles.panelHeader}>
        <div>
          <span className={styles.eyebrow}>Change list review</span>
          <h3>{changeList.title}</h3>
        </div>
        <StatusBadge
          tone={
            headerStatus === "approved" ? "ok" : headerStatus === "pending" || !headerStatus ? "neutral" : "warn"
          }
        >
          {formatStatus(headerStatus)}
        </StatusBadge>
      </header>

      <div className={styles.panelBody}>
        <MetaGrid
          items={[
            { label: "Client", value: changeList.clientId || "—" },
            { label: "Due", value: changeList.dueDate ? formatDate(changeList.dueDate) : "Not set" },
            {
              label: "Priority",
              value: changeList.priority ? <PriorityBadge priority={changeList.priority} /> : undefined,
            },
            { label: "Lines", value: String(changeList.lines.length) },
          ]}
        />

        {incompleteCount > 0 ? (
          <p className={styles.banner} role="status">
            {incompleteCount} incomplete line{incompleteCount === 1 ? "" : "s"} — you can still approve
            as a HITL override.
          </p>
        ) : null}

        <span className={styles.sectionLabel}>Field changes</span>
        <div className={styles.lines} aria-label="Change list lines">
          {changeList.lines.length === 0 ? (
            <p className={styles.hint}>No field changes were extracted for this change list yet.</p>
          ) : (
            changeList.lines.map((line, index) => (
              <section
                key={line.id}
                className={
                  line.incomplete ? `${styles.lineCard} ${styles.lineCardIncomplete}` : styles.lineCard
                }
                aria-label={humanizeField(line.field)}
              >
                <header className={styles.lineHeader}>
                  <span className={styles.lineIndex}>#{index + 1}</span>
                  <span className={styles.lineField} title={line.field}>
                    {humanizeField(line.field)}
                  </span>
                  {line.incomplete ? <span className={styles.incompleteChip}>Incomplete</span> : null}
                </header>
                <div className={styles.delta}>
                  <div className={styles.valueBlock}>
                    <span className={styles.fieldLabel}>From</span>
                    <span className={styles.value}>{line.from ?? "—"}</span>
                  </div>
                  <span className={styles.deltaArrow} aria-hidden>
                    →
                  </span>
                  <div className={styles.valueBlock}>
                    <span className={styles.fieldLabel}>To</span>
                    <span className={`${styles.value} ${styles.valueTo}`}>{line.to ?? "—"}</span>
                  </div>
                </div>
                {line.effectiveDate || line.recommendedSystem ? (
                  <footer className={styles.lineMeta}>
                    {line.effectiveDate ? (
                      <span className={styles.metaChip}>Effective {formatDate(line.effectiveDate)}</span>
                    ) : null}
                    {line.recommendedSystem ? (
                      <span className={styles.metaChip}>
                        {line.recommendedSystem}
                        {line.recommendedField ? ` · ${line.recommendedField}` : ""}
                      </span>
                    ) : null}
                  </footer>
                ) : null}
              </section>
            ))
          )}
        </div>
        <ErrorBox label="Change list action failed" message={error} />
      </div>

      {!decided ? (
        <div className={styles.actions}>
          <button className="btn-primary" type="button" disabled={busy} onClick={() => void decide("approved")}>
            Approve
          </button>
          <button type="button" disabled={busy} onClick={() => void decide("needs_clarification")}>
            Needs clarification
          </button>
        </div>
      ) : null}
    </article>
  );
}
