import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { DraftsError, fetchDrafts, updateDraftStatus } from "../api/drafts";
import { useSpecialist } from "../auth/useSpecialist";
import { EmptyState } from "../components/EmptyState";
import { MarkdownBody } from "../components/MarkdownBody";
import { MasterDetail } from "../components/MasterDetail";
import { Toast } from "../components/Toast";
import { animateEnter } from "../lib/animateEnter";
import type { DraftItem } from "../types/domain";
import styles from "./DraftsPage.module.css";

function formatStatus(status: DraftItem["status"]) {
  switch (status) {
    case "pending":
      return "Pending review";
    case "accepted":
      return "Accepted";
    case "discarded":
      return "Discarded";
    case "sent":
      return "Sent";
  }
}

export function DraftsPage() {
  const rootRef = useRef<HTMLDivElement>(null);
  const [searchParams] = useSearchParams();
  const { getAccessToken, specialistId } = useSpecialist();
  const [drafts, setDrafts] = useState<DraftItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editBody, setEditBody] = useState("");
  const [isEditing, setIsEditing] = useState(false);
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

  const loadDrafts = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    const preferId = searchParams.get("id");
    try {
      const token = await getAccessToken();
      const next = await fetchDrafts(specialistId, token);
      setDrafts(next);
      setSelectedId((current) => {
        if (preferId && next.some((item) => item.id === preferId)) {
          return preferId;
        }
        return current && next.some((item) => item.id === current) ? current : null;
      });
      if (preferId) {
        const match = next.find((item) => item.id === preferId);
        if (match) {
          setEditBody(match.body ?? "");
          setIsEditing(false);
        } else {
          setToast("Draft not found for that queue item");
        }
      }
    } catch (caught) {
      setDrafts([]);
      setLoadError(
        caught instanceof DraftsError || caught instanceof Error
          ? caught.message
          : "Unable to load drafts.",
      );
    } finally {
      setIsLoading(false);
    }
  }, [getAccessToken, searchParams, specialistId]);

  useEffect(() => {
    void loadDrafts();
  }, [loadDrafts]);

  const selectedDraft = drafts.find((draft) => draft.id === selectedId) ?? null;
  const hasDrafts = drafts.length > 0;
  const hasSelection = selectedDraft !== null;

  function handleSelect(id: string) {
    const draft = drafts.find((item) => item.id === id);
    setSelectedId(id);
    setEditBody(draft?.body ?? "");
    setIsEditing(false);
  }

  function handleEditToggle() {
    if (!hasSelection) {
      return;
    }

    setIsEditing((editing) => !editing);
  }

  async function handleStatus(status: "accepted" | "discarded") {
    if (!selectedDraft) {
      return;
    }
    setIsUpdating(true);
    setToast(null);
    try {
      const token = await getAccessToken();
      await updateDraftStatus(specialistId, selectedDraft.id, status, {
        body: isEditing ? editBody : undefined,
        token,
      });
      setDrafts((current) => current.filter((item) => item.id !== selectedDraft.id));
      setSelectedId(null);
      setIsEditing(false);
      setToast(status === "accepted" ? "Draft accepted." : "Draft discarded.");
    } catch (caught) {
      setToast(
        caught instanceof DraftsError || caught instanceof Error
          ? caught.message
          : "Unable to update draft.",
      );
    } finally {
      setIsUpdating(false);
    }
  }

  const hitlActions = (
    <div aria-label="Draft review actions" className={styles.actions}>
      <button
        className="btn-primary"
        disabled={!hasSelection || isUpdating}
        type="button"
        onClick={() => void handleStatus("accepted")}
      >
        Accept
      </button>
      <button disabled={!hasSelection} type="button" onClick={handleEditToggle}>
        {isEditing ? "Preview" : "Edit"}
      </button>
      <button
        disabled={!hasSelection || isUpdating}
        type="button"
        onClick={() => void handleStatus("discarded")}
      >
        Discard
      </button>
      <button
        disabled={!hasSelection}
        type="button"
        onClick={() => setToast("Not connected yet")}
      >
        Send
      </button>
    </div>
  );

  const list = (
    <div className={styles.listStack}>
      {isLoading ? (
        <div className={styles.listEmpty} data-enter>
          <span className={styles.emptyKicker}>Loading</span>
          <span>Fetching pending drafts…</span>
        </div>
      ) : loadError ? (
        <div className={styles.listEmpty} data-enter>
          <span className={styles.emptyKicker}>Unable to load</span>
          <span>{loadError}</span>
          <button type="button" onClick={() => void loadDrafts()}>
            Retry
          </button>
        </div>
      ) : hasDrafts ? (
        drafts.map((draft) => {
          const isSelected = draft.id === selectedId;

          return (
            <button
              aria-pressed={isSelected}
              className={isSelected ? `${styles.row} ${styles.selected}` : styles.row}
              data-enter
              key={draft.id}
              type="button"
              onClick={() => handleSelect(draft.id)}
            >
              <span className={styles.rowMeta}>
                <span className={styles.status}>{formatStatus(draft.status)}</span>
              </span>
              <span className={styles.subject}>{draft.subject}</span>
              <span className={styles.recipient}>To: {draft.to}</span>
            </button>
          );
        })
      ) : (
        <div className={styles.listEmpty} data-enter>
          <span className={styles.emptyKicker}>No drafts</span>
          <span>No pending drafts in Neon. Run triage with drafting enabled to populate this list.</span>
        </div>
      )}
    </div>
  );

  const detail = loadError ? (
    <div className={styles.detailShell}>
      <EmptyState title="Drafts unavailable" detail={loadError} />
      <button type="button" onClick={() => void loadDrafts()}>
        Retry
      </button>
    </div>
  ) : !hasDrafts ? (
    <div className={styles.detailShell}>
      <EmptyState
        title={isLoading ? "Loading drafts" : "No pending drafts"}
        detail={
          isLoading
            ? "Fetching drafted responses from Neon…"
            : "Accepted or discarded drafts leave this list. Run triage to generate new drafts."
        }
      />
      {hitlActions}
    </div>
  ) : selectedDraft ? (
    <article className={styles.detail} data-enter>
      <div className={styles.detailHeader}>
        <div>
          <span className={styles.eyebrow}>Draft review</span>
          <h2>{selectedDraft.subject}</h2>
        </div>
        <span className={styles.statusBadge}>{formatStatus(selectedDraft.status)}</span>
      </div>

      <div className={styles.detailMeta}>
        <div>
          <span>To</span>
          <strong>{selectedDraft.to}</strong>
        </div>
        {selectedDraft.relatedQueueId ? (
          <div>
            <span>Related queue item</span>
            <strong>{selectedDraft.relatedQueueId}</strong>
          </div>
        ) : null}
      </div>

      {isEditing ? (
        <label className={styles.editor}>
          <span>Response body</span>
          <textarea
            aria-label="Draft response body"
            rows={12}
            value={editBody}
            onChange={(event) => setEditBody(event.target.value)}
          />
        </label>
      ) : (
        <div className={styles.bodyPreview}>
          <span className={styles.bodyLabel}>Response body</span>
          <MarkdownBody
            source={selectedDraft.body}
            emptyLabel="No draft body has been generated yet."
          />
        </div>
      )}

      {hitlActions}
    </article>
  ) : (
    <div className={styles.detailShell}>
      <div className={styles.selectPrompt} data-enter>
        <span className={styles.emptyKicker}>Select a draft</span>
        <p>Choose a draft from the list to review the response and take HITL action.</p>
      </div>
      {hitlActions}
    </div>
  );

  return (
    <div className={styles.page} ref={rootRef}>
      <section className={styles.toolbar} data-enter>
        <div>
          <span className={styles.eyebrow}>Human in the loop</span>
          <h2>Draft responses</h2>
        </div>
        <p className={styles.toolbarNote}>
          Review agent-generated payroll replies before they leave the workbench.
        </p>
      </section>

      <MasterDetail detail={detail} list={list} listLabel="Draft items" />
      <Toast message={toast} onDismiss={() => setToast(null)} />
    </div>
  );
}
