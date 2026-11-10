import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchQueue, patchQueueItem, QueueError } from "../api/queue";
import { useSpecialist } from "../auth/useSpecialist";
import { CategoryChip } from "../components/CategoryChip";
import { EmptyState } from "../components/EmptyState";
import { MasterDetail } from "../components/MasterDetail";
import { PriorityBadge } from "../components/PriorityBadge";
import { Toast } from "../components/Toast";
import { animateEnter } from "../lib/animateEnter";
import { sortQueueItems } from "../lib/queueSort";
import type { Category, Priority, QueueItem } from "../types/domain";
import styles from "./QueuePage.module.css";

type CategoryFilter = "all" | Category;
type PriorityFilter = "all" | Priority;

const categoryOptions: { label: string; value: CategoryFilter }[] = [
  { label: "All categories", value: "all" },
  { label: "Q&A", value: "qa" },
  { label: "Change list", value: "changelist" },
  { label: "Todo", value: "todo" },
  { label: "Out of scope", value: "out_of_scope" },
];

const priorityOptions: { label: string; value: PriorityFilter }[] = [
  { label: "All priorities", value: "all" },
  { label: "P1", value: 1 },
  { label: "P2", value: 2 },
  { label: "P3", value: 3 },
  { label: "P4", value: 4 },
  { label: "P5", value: 5 },
];

const priorityValues: Priority[] = [1, 2, 3, 4, 5];

function parsePriorityFilter(value: string): PriorityFilter {
  return value === "all" ? "all" : (Number(value) as Priority);
}

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

function getErrorDetail(error: unknown) {
  if (error instanceof QueueError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unable to load the queue.";
}

export function QueuePage() {
  const rootRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { getAccessToken, specialistId } = useSpecialist();
  const [items, setItems] = useState<QueueItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>("all");
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>("all");
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

  const loadQueue = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const token = await getAccessToken();
      const next = await fetchQueue(specialistId, token);
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
  }, [getAccessToken, specialistId]);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  const filteredItems = useMemo(() => {
    return sortQueueItems(items).filter((item) => {
      const matchesCategory = categoryFilter === "all" || item.category === categoryFilter;
      const matchesPriority = priorityFilter === "all" || item.priority === priorityFilter;
      return matchesCategory && matchesPriority;
    });
  }, [categoryFilter, items, priorityFilter]);

  const selectedItem = filteredItems.find((item) => item.id === selectedId) ?? null;
  const hasItems = items.length > 0;
  const hasFilteredItems = filteredItems.length > 0;

  async function handleMarkDone() {
    if (!selectedItem || isUpdating) {
      return;
    }
    setIsUpdating(true);
    setToast(null);
    try {
      const token = await getAccessToken();
      await patchQueueItem(specialistId, selectedItem.id, { done: true }, token);
      setToast("Marked done");
      await loadQueue();
    } catch (caught) {
      setToast(getErrorDetail(caught));
    } finally {
      setIsUpdating(false);
    }
  }

  async function handlePriorityChange(next: Priority) {
    if (!selectedItem || isUpdating || next === selectedItem.priority) {
      return;
    }
    setIsUpdating(true);
    setToast(null);
    try {
      const token = await getAccessToken();
      const updated = await patchQueueItem(
        specialistId,
        selectedItem.id,
        { priority: next },
        token,
      );
      setItems((current) =>
        current.map((item) => (item.id === updated.id ? { ...item, ...updated } : item)),
      );
      setToast(`Priority set to P${next}`);
    } catch (caught) {
      setToast(getErrorDetail(caught));
    } finally {
      setIsUpdating(false);
    }
  }

  function handleOpenDraft() {
    if (!selectedItem) {
      return;
    }
    if (!selectedItem.hasDraft) {
      setToast("No draft for this item");
      return;
    }
    navigate(`/drafts?id=${encodeURIComponent(selectedItem.id)}`);
  }

  function handleOpenChangeList() {
    if (!selectedItem) {
      return;
    }
    if (selectedItem.category !== "changelist") {
      setToast("This item is not a change list");
      return;
    }
    navigate(`/change-lists?id=${encodeURIComponent(selectedItem.id)}`);
  }

  const list = (
    <div className={styles.listStack}>
      {isLoading ? (
        <div className={styles.listEmpty} data-enter>
          <span className={styles.emptyKicker}>Loading</span>
          <span>Fetching open queue items from Neon…</span>
        </div>
      ) : loadError ? (
        <div className={styles.listEmpty} data-enter role="alert">
          <span className={styles.emptyKicker}>Queue unavailable</span>
          <span>{loadError}</span>
          <button type="button" onClick={() => void loadQueue()} style={{ marginTop: "0.75rem" }}>
            Retry
          </button>
        </div>
      ) : hasFilteredItems ? (
        filteredItems.map((item) => {
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
                <PriorityBadge priority={item.priority} />
                <CategoryChip category={item.category} />
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
          <span className={styles.emptyKicker}>{hasItems ? "No matches" : "Queue idle"}</span>
          <span>
            {hasItems
              ? "Adjust filters to widen the work queue."
              : "Incoming payroll work will appear here after triage writes categorized emails to Neon."}
          </span>
        </div>
      )}
    </div>
  );

  const detail = loadError ? (
    <EmptyState
      title="Cannot load queue"
      detail={loadError}
    />
  ) : isLoading ? (
    <EmptyState title="Loading queue" detail="Requesting open items from GET /queue." />
  ) : !hasItems ? (
    <EmptyState
      title="Queue ready"
      detail="No open categorized items in Neon yet. Run triage with DATABASE_URL set to populate this list."
    />
  ) : selectedItem ? (
    <article className={styles.detail} data-enter>
      <div className={styles.detailHeader}>
        <div>
          <span className={styles.eyebrow}>Queue detail</span>
          <h2>{selectedItem.subject}</h2>
        </div>
        <div className={styles.badges}>
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

      <div className={styles.actions} aria-label="Queue actions">
        <button
          className="btn-primary"
          type="button"
          disabled={isUpdating}
          onClick={handleOpenDraft}
        >
          Open draft
        </button>
        {selectedItem.category === "changelist" ? (
          <button type="button" disabled={isUpdating} onClick={handleOpenChangeList}>
            Open change list
          </button>
        ) : null}
        <button type="button" disabled={isUpdating} onClick={() => void handleMarkDone()}>
          Mark done
        </button>
        <label className={styles.priorityAdjust}>
          <span>Adjust priority</span>
          <select
            aria-label="Adjust priority"
            value={selectedItem.priority}
            disabled={isUpdating}
            onChange={(event) => void handlePriorityChange(Number(event.target.value) as Priority)}
          >
            {priorityValues.map((priority) => (
              <option key={priority} value={priority}>
                P{priority}
              </option>
            ))}
          </select>
        </label>
      </div>
    </article>
  ) : (
    <div className={styles.selectPrompt} data-enter>
      <span className={styles.emptyKicker}>Select an item</span>
      <p>Choose a queue row to inspect extracted payroll context and action controls.</p>
    </div>
  );

  return (
    <div className={styles.page} ref={rootRef}>
      <section className={styles.toolbar} aria-label="Queue filters" data-enter>
        <div>
          <span className={styles.eyebrow}>Work queue</span>
          <h2>Payroll intake</h2>
        </div>
        <div className={styles.filters}>
          <label>
            <span>Category</span>
            <select
              value={categoryFilter}
              onChange={(event) => setCategoryFilter(event.target.value as CategoryFilter)}
            >
              {categoryOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Priority</span>
            <select
              value={priorityFilter}
              onChange={(event) => setPriorityFilter(parsePriorityFilter(event.target.value))}
            >
              {priorityOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <button type="button" onClick={() => void loadQueue()} disabled={isLoading}>
            {isLoading ? "Refreshing" : "Refresh"}
          </button>
        </div>
      </section>

      <MasterDetail detail={detail} list={list} listLabel="Queue items" />
      <Toast message={toast} onDismiss={() => setToast(null)} />
    </div>
  );
}
