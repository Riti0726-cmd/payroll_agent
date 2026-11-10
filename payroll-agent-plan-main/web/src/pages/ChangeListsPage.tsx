import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ChangeListsError,
  fetchChangeLists,
  patchChangeList,
} from "../api/changelists";
import { useSpecialist } from "../auth/useSpecialist";
import { EmptyState } from "../components/EmptyState";
import { MasterDetail } from "../components/MasterDetail";
import { PriorityBadge } from "../components/PriorityBadge";
import { Toast } from "../components/Toast";
import { animateEnter } from "../lib/animateEnter";
import type { ChangeListItem } from "../types/domain";
import styles from "./ChangeListsPage.module.css";

type EditableLine = ChangeListItem["lines"][number];

function formatStatus(status: ChangeListItem["status"]) {
  if (status === "incomplete") {
    return "Incomplete";
  }
  return "Pending review";
}

function formatDueDate(dueDate: string) {
  const date = new Date(dueDate);
  if (Number.isNaN(date.getTime())) {
    return dueDate;
  }
  return new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

export function ChangeListsPage() {
  const rootRef = useRef<HTMLDivElement>(null);
  const [searchParams] = useSearchParams();
  const { getAccessToken, specialistId } = useSpecialist();
  const [changeLists, setChangeLists] = useState<ChangeListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editedLines, setEditedLines] = useState<EditableLine[]>([]);
  const [isUpdating, setIsUpdating] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    animateEnter(rootRef.current);
  }, []);

  useEffect(() => {
    if (!toast) {
      return undefined;
    }

    const timeout = window.setTimeout(() => setToast(null), 2800);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const loadChangeLists = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    const preferId = searchParams.get("id");
    try {
      const token = await getAccessToken();
      const next = await fetchChangeLists(specialistId, token);
      setChangeLists(next);
      setSelectedId((current) => {
        if (preferId && next.some((item) => item.id === preferId)) {
          return preferId;
        }
        return current && next.some((item) => item.id === current) ? current : null;
      });
      if (preferId && !next.some((item) => item.id === preferId)) {
        setToast("Change list not found for that queue item");
      }
    } catch (caught) {
      setChangeLists([]);
      setLoadError(
        caught instanceof ChangeListsError || caught instanceof Error
          ? caught.message
          : "Unable to load change lists.",
      );
    } finally {
      setIsLoading(false);
    }
  }, [getAccessToken, searchParams, specialistId]);

  useEffect(() => {
    void loadChangeLists();
  }, [loadChangeLists]);

  const selectedChangeList = changeLists.find((item) => item.id === selectedId) ?? null;
  const hasChangeLists = changeLists.length > 0;

  useEffect(() => {
    if (selectedChangeList) {
      setEditedLines(selectedChangeList.lines.map((line) => ({ ...line })));
    } else {
      setEditedLines([]);
    }
  }, [selectedChangeList]);

  function updateLine(lineId: string, patch: Partial<EditableLine>) {
    setEditedLines((current) =>
      current.map((line) => (line.id === lineId ? { ...line, ...patch } : line)),
    );
  }

  function toggleLine(lineId: string) {
    setEditedLines((current) =>
      current.map((line) =>
        line.id === lineId ? { ...line, reviewed: !line.reviewed } : line,
      ),
    );
  }

  async function handleSaveLines() {
    if (!selectedChangeList || isUpdating) {
      return;
    }
    setIsUpdating(true);
    setToast(null);
    try {
      const token = await getAccessToken();
      const updated = await patchChangeList(
        specialistId,
        selectedChangeList.id,
        { lines: editedLines },
        token,
      );
      setChangeLists((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      setToast("Line edits saved.");
    } catch (caught) {
      setToast(
        caught instanceof ChangeListsError || caught instanceof Error
          ? caught.message
          : "Unable to save line edits.",
      );
    } finally {
      setIsUpdating(false);
    }
  }

  async function handleStatus(status: "approved" | "needs_clarification") {
    if (!selectedChangeList) {
      return;
    }
    setIsUpdating(true);
    setToast(null);
    try {
      const token = await getAccessToken();
      await patchChangeList(
        specialistId,
        selectedChangeList.id,
        { status, lines: editedLines },
        token,
      );
      setChangeLists((current) => current.filter((item) => item.id !== selectedChangeList.id));
      setSelectedId(null);
      setToast(status === "approved" ? "Change list approved." : "Clarification requested.");
    } catch (caught) {
      setToast(
        caught instanceof ChangeListsError || caught instanceof Error
          ? caught.message
          : "Unable to update change list.",
      );
    } finally {
      setIsUpdating(false);
    }
  }

  const incompleteCount = editedLines.filter((line) => line.incomplete).length;
  const reviewedCount = editedLines.filter((line) => line.reviewed).length;

  const actions = (
    <div aria-label="Change list actions" className={styles.actions}>
      <button type="button" disabled={!selectedChangeList || isUpdating} onClick={() => void handleSaveLines()}>
        Save edits
      </button>
      <button
        className="btn-primary"
        type="button"
        disabled={!selectedChangeList || isUpdating}
        onClick={() => void handleStatus("approved")}
      >
        Approve
      </button>
      <button
        type="button"
        disabled={!selectedChangeList || isUpdating}
        onClick={() => void handleStatus("needs_clarification")}
      >
        Request clarification
      </button>
    </div>
  );

  const list = (
    <div className={styles.listStack}>
      {isLoading ? (
        <div className={styles.listEmpty} data-enter>
          <span className={styles.emptyKicker}>Loading</span>
          <span>Fetching categorized changelist rows from Neon…</span>
        </div>
      ) : loadError ? (
        <div className={styles.listEmpty} data-enter role="alert">
          <span className={styles.emptyKicker}>Unavailable</span>
          <span>{loadError}</span>
          <button type="button" className={styles.retryInline} onClick={() => void loadChangeLists()}>
            Retry
          </button>
        </div>
      ) : hasChangeLists ? (
        changeLists.map((item) => {
          const isSelected = item.id === selectedId;
          const incomplete = item.status === "incomplete" || item.lines.some((line) => line.incomplete);
          return (
            <button
              aria-pressed={isSelected}
              className={isSelected ? `${styles.row} ${styles.selected}` : styles.row}
              data-enter
              key={item.id}
              type="button"
              onClick={() => setSelectedId(item.id)}
            >
              <span className={styles.rowMeta}>
                <span className={styles.clientChip}>{item.clientId || "No client"}</span>
                {item.priority ? <PriorityBadge priority={item.priority} /> : null}
                <span className={incomplete ? styles.statusWarn : styles.status}>
                  {formatStatus(incomplete ? "incomplete" : item.status)}
                </span>
              </span>
              <span className={styles.subject}>{item.title}</span>
              <span className={styles.rowFooter}>
                <span className={styles.lineCount}>
                  {item.lines.length} field{item.lines.length === 1 ? "" : "s"}
                </span>
                {item.dueDate ? (
                  <span className={styles.dueHint}>Due {formatDueDate(item.dueDate)}</span>
                ) : null}
              </span>
            </button>
          );
        })
      ) : (
        <div className={styles.listEmpty} data-enter>
          <span className={styles.emptyKicker}>No change lists</span>
          <span>No pending changelist items in Neon. Run triage to categorize updates.</span>
        </div>
      )}
    </div>
  );

  const detail = loadError ? (
    <div className={styles.detailShell}>
      <EmptyState title="Change lists unavailable" detail={loadError} />
      <button type="button" onClick={() => void loadChangeLists()}>
        Retry
      </button>
    </div>
  ) : !hasChangeLists ? (
    <div className={styles.detailShell}>
      <EmptyState
        title={isLoading ? "Loading change lists" : "No pending change lists"}
        detail={
          isLoading
            ? "Fetching categorized changelist rows from Neon…"
            : "Approved items leave this list. Open a row to review field changes when present."
        }
      />
      {actions}
    </div>
  ) : selectedChangeList ? (
    <article className={styles.detail} data-enter>
      <div className={styles.detailHeader}>
        <div>
          <span className={styles.eyebrow}>Change list review</span>
          <h2>{selectedChangeList.title}</h2>
        </div>
        <span
          className={
            selectedChangeList.status === "incomplete" || incompleteCount > 0
              ? `${styles.statusBadge} ${styles.statusBadgeWarn}`
              : styles.statusBadge
          }
        >
          {formatStatus(
            incompleteCount > 0 ? "incomplete" : selectedChangeList.status,
          )}
        </span>
      </div>

      <div className={styles.detailMeta}>
        <div>
          <span>Client</span>
          <strong>{selectedChangeList.clientId || "—"}</strong>
        </div>
        <div>
          <span>Due</span>
          <strong>
            {selectedChangeList.dueDate ? formatDueDate(selectedChangeList.dueDate) : "Not set"}
          </strong>
        </div>
        <div>
          <span>Priority</span>
          <strong>
            {selectedChangeList.priority ? (
              <PriorityBadge priority={selectedChangeList.priority} />
            ) : (
              "—"
            )}
          </strong>
        </div>
        <div>
          <span>Review</span>
          <strong>
            {reviewedCount}/{editedLines.length} marked
          </strong>
        </div>
      </div>

      {incompleteCount > 0 ? (
        <p className={styles.banner} role="status">
          {incompleteCount} incomplete line{incompleteCount === 1 ? "" : "s"} — you can still
          approve as a HITL override.
        </p>
      ) : null}

      <div className={styles.linesSection}>
        <span className={styles.sectionLabel}>Field changes</span>
        <div className={styles.lines} aria-label="Change list lines">
          {editedLines.length === 0 ? (
            <div className={styles.emptyLines}>
              <span className={styles.emptyKicker}>No lines</span>
              <p>No field changes were extracted for this changelist yet.</p>
            </div>
          ) : (
            editedLines.map((line, index) => (
              <article
                className={
                  line.incomplete
                    ? `${styles.lineCard} ${styles.lineCardIncomplete}`
                    : line.reviewed
                      ? `${styles.lineCard} ${styles.lineCardReviewed}`
                      : styles.lineCard
                }
                key={line.id}
              >
                <header className={styles.lineHeader}>
                  <span className={styles.lineIndex}>#{index + 1}</span>
                  <label className={styles.reviewToggle}>
                    <input
                      type="checkbox"
                      checked={line.reviewed}
                      onChange={() => toggleLine(line.id)}
                    />
                    <span>{line.reviewed ? "Reviewed" : "Mark reviewed"}</span>
                  </label>
                  {line.incomplete ? (
                    <span className={styles.incompleteChip}>Incomplete</span>
                  ) : null}
                </header>

                <label className={styles.fieldBlock}>
                  <span>Field</span>
                  <input
                    aria-label={`Field ${line.id}`}
                    value={line.field}
                    onChange={(event) => updateLine(line.id, { field: event.target.value })}
                  />
                </label>

                <div className={styles.delta}>
                  <label className={styles.valueBlock}>
                    <span>From</span>
                    <input
                      aria-label={`From ${line.id}`}
                      placeholder="Previous value"
                      value={line.from ?? ""}
                      onChange={(event) =>
                        updateLine(line.id, { from: event.target.value || undefined })
                      }
                    />
                  </label>
                  <span className={styles.deltaArrow} aria-hidden>
                    →
                  </span>
                  <label className={styles.valueBlock}>
                    <span>To</span>
                    <input
                      aria-label={`To ${line.id}`}
                      placeholder="New value"
                      value={line.to ?? ""}
                      onChange={(event) =>
                        updateLine(line.id, { to: event.target.value || undefined })
                      }
                    />
                  </label>
                </div>

                {(line.effectiveDate || line.recommendedSystem || line.recommendedField) && (
                  <footer className={styles.lineMeta}>
                    {line.effectiveDate ? (
                      <span className={styles.metaChip}>Effective {line.effectiveDate}</span>
                    ) : null}
                    {line.recommendedSystem ? (
                      <span className={styles.metaChip}>
                        {line.recommendedSystem}
                        {line.recommendedField ? ` · ${line.recommendedField}` : ""}
                      </span>
                    ) : null}
                  </footer>
                )}
              </article>
            ))
          )}
        </div>
      </div>

      {actions}
    </article>
  ) : (
    <div className={styles.detailShell}>
      <div className={styles.selectPrompt} data-enter>
        <span className={styles.emptyKicker}>Select a change list</span>
        <p>Choose a generated change list to review field updates before approval.</p>
      </div>
      {actions}
    </div>
  );

  return (
    <div className={styles.page} ref={rootRef}>
      <section className={styles.toolbar} data-enter>
        <div>
          <span className={styles.eyebrow}>Payroll changes</span>
          <h2>Change lists</h2>
        </div>
        <p className={styles.toolbarNote}>
          Review generated payroll updates before they are approved for downstream action.
        </p>
      </section>

      <MasterDetail detail={detail} list={list} listLabel="Change lists" />
      <Toast message={toast} onDismiss={() => setToast(null)} />
    </div>
  );
}
