import { useCallback, useEffect, useRef, useState } from "react";
import { fetchHistory, HistoryError } from "../api/history";
import { useSpecialist } from "../auth/useSpecialist";
import { CategoryChip } from "../components/CategoryChip";
import { EmptyState } from "../components/EmptyState";
import { MasterDetail } from "../components/MasterDetail";
import { PriorityBadge } from "../components/PriorityBadge";
import { animateEnter } from "../lib/animateEnter";
import type { HistoryItem, HistoryStatus } from "../types/domain";
import styles from "./QueuePage.module.css";

type StatusFilter = "all" | HistoryStatus;

const statusOptions: { label: string; value: StatusFilter }[] = [
  { label: "All closed", value: "all" },
  { label: "Done", value: "done" },
  { label: "Accepted", value: "accepted" },
  { label: "Discarded", value: "discarded" },
  { label: "Approved", value: "approved" },
  { label: "Needs clarification", value: "needs_clarification" },
];

function formatReceivedAt(receivedAt: string) {
  const date = new Date(receivedAt);
  if (Number.isNaN(date.getTime())) {
    return receivedAt;
  }
  return new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
  }).format(date);
}

function formatStatus(status: HistoryStatus) {
  switch (status) {
    case "done":
      return "Done";
    case "accepted":
      return "Accepted";
    case "discarded":
      return "Discarded";
    case "approved":
      return "Approved";
    case "needs_clarification":
      return "Needs clarification";
  }
}

function getErrorDetail(error: unknown) {
  if (error instanceof HistoryError || error instanceof Error) {
    return error.message;
  }
  return "Unable to load history.";
}

export function HistoryPage() {
  const rootRef = useRef<HTMLDivElement>(null);
  const { getAccessToken, specialistId } = useSpecialist();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  useEffect(() => {
    animateEnter(rootRef.current);
  }, []);

  const loadHistory = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const token = await getAccessToken();
      const next = await fetchHistory(specialistId, statusFilter, token);
      setItems(next);
      setSelectedId((current) =>
        current && next.some((item) => item.id === current) ? current : null,
      );
    } catch (caught) {
      setItems([]);
      setSelectedId(null);
      setLoadError(getErrorDetail(caught));
    } finally {
      setIsLoading(false);
    }
  }, [getAccessToken, specialistId, statusFilter]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  const selectedItem = items.find((item) => item.id === selectedId) ?? null;
  const hasItems = items.length > 0;

  const list = (
    <div className={styles.listStack}>
      {isLoading ? (
        <div className={styles.listEmpty} data-enter>
          <span className={styles.emptyKicker}>Loading</span>
          <span>Fetching closed items from Neon…</span>
        </div>
      ) : loadError ? (
        <div className={styles.listEmpty} data-enter role="alert">
          <span className={styles.emptyKicker}>History unavailable</span>
          <span>{loadError}</span>
          <button type="button" onClick={() => void loadHistory()} style={{ marginTop: "0.75rem" }}>
            Retry
          </button>
        </div>
      ) : hasItems ? (
        items.map((item) => {
          const isSelected = item.id === selectedId;
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
                <span className={styles.status}>{formatStatus(item.status)}</span>
                <CategoryChip category={item.category} />
                <PriorityBadge priority={item.priority} />
                <span className={styles.timestamp}>{formatReceivedAt(item.receivedAt)}</span>
              </span>
              <span className={styles.subject}>{item.subject}</span>
              <span className={styles.rowFooter}>
                <span>{item.clientId ?? "Client pending"}</span>
                <span>{item.employeeId ?? "Employee pending"}</span>
              </span>
            </button>
          );
        })
      ) : (
        <div className={styles.listEmpty} data-enter>
          <span className={styles.emptyKicker}>No history</span>
          <span>Closed items (done, accepted, discarded, approved) will appear here.</span>
        </div>
      )}
    </div>
  );

  const detail = loadError ? (
    <EmptyState title="Cannot load history" detail={loadError} />
  ) : isLoading ? (
    <EmptyState title="Loading history" detail="Requesting closed items from GET /history." />
  ) : !hasItems ? (
    <EmptyState
      title="History ready"
      detail="No closed HITL items for this mailbox yet. Mark queue items done or complete drafts to fill this list."
    />
  ) : selectedItem ? (
    <article className={styles.detail} data-enter>
      <div className={styles.detailHeader}>
        <div>
          <span className={styles.eyebrow}>History detail</span>
          <h2>{selectedItem.subject}</h2>
        </div>
        <div className={styles.badges}>
          <span className={styles.statusBadge}>{formatStatus(selectedItem.status)}</span>
          <PriorityBadge priority={selectedItem.priority} />
          <CategoryChip category={selectedItem.category} />
        </div>
      </div>
      <div className={styles.detailGrid}>
        <div>
          <span>Received</span>
          <strong>{formatReceivedAt(selectedItem.receivedAt)}</strong>
        </div>
        <div>
          <span>Client</span>
          <strong>{selectedItem.clientId ?? "Pending"}</strong>
        </div>
        <div>
          <span>Employee</span>
          <strong>{selectedItem.employeeId ?? "Pending"}</strong>
        </div>
      </div>
      <p className={styles.excerpt}>
        {selectedItem.bodyExcerpt ?? "No message excerpt has been extracted yet."}
      </p>
      {selectedItem.extracted ? (
        <dl className={styles.extracted}>
          {Object.entries(selectedItem.extracted).map(([key, value]) => (
            <div key={key}>
              <dt>{key}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </article>
  ) : (
    <div className={styles.selectPrompt} data-enter>
      <span className={styles.emptyKicker}>Select an item</span>
      <p>Choose a closed item to inspect status and extracted context.</p>
    </div>
  );

  return (
    <div className={styles.page} ref={rootRef}>
      <section className={styles.toolbar} aria-label="History filters" data-enter>
        <div>
          <span className={styles.eyebrow}>Closed work</span>
          <h2>History</h2>
        </div>
        <div className={styles.filters}>
          <label>
            <span>Status</span>
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
            >
              {statusOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <button type="button" onClick={() => void loadHistory()} disabled={isLoading}>
            {isLoading ? "Refreshing" : "Refresh"}
          </button>
        </div>
      </section>
      <MasterDetail detail={detail} list={list} listLabel="History items" />
    </div>
  );
}
