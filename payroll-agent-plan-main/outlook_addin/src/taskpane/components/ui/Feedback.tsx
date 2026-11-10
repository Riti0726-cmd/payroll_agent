// Ports of web/src/components/{EmptyState,Toast}.tsx and the pages' kicker/error blocks.
import * as React from "react";
import styles from "./ui.module.css";

export function EmptyState({
  kicker,
  title,
  detail,
  children,
}: {
  kicker?: string;
  title: string;
  detail?: string;
  children?: React.ReactNode;
}) {
  return (
    <section className={styles.empty} data-enter aria-label={title}>
      {kicker ? <span className={styles.kicker}>{kicker}</span> : null}
      <h2 className={styles.emptyTitle}>{title}</h2>
      {detail ? <p className={styles.emptyDetail}>{detail}</p> : null}
      {children}
    </section>
  );
}

/** Small inline "Loading / Unable to load" block used inside lists and panels. */
export function InlineNote({ kicker, children }: { kicker: string; children: React.ReactNode }) {
  return (
    <div className={styles.note} data-enter>
      <span className={styles.kicker}>{kicker}</span>
      <span>{children}</span>
    </div>
  );
}

export function ErrorBox({
  label = "Request failed",
  message,
  onRetry,
}: {
  label?: string;
  message: string | null;
  onRetry?: () => void;
}) {
  if (!message) return null;
  return (
    <div className={styles.errorBox} role="alert">
      <div>
        <span className={styles.errorLabel}>{label}</span>
        <p>{message}</p>
      </div>
      {onRetry ? (
        <button type="button" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function Toast({ message, onDismiss }: { message: string | null; onDismiss: () => void }) {
  React.useEffect(() => {
    if (!message) return undefined;
    const timer = window.setTimeout(onDismiss, 4000);
    return () => window.clearTimeout(timer);
  }, [message, onDismiss]);

  if (!message) return null;
  return (
    <div className={styles.toast} role="status" aria-live="polite">
      <span>{message}</span>
      <button type="button" onClick={onDismiss}>
        Dismiss
      </button>
    </div>
  );
}

/** Uppercase label + bold value tile (web .detailMeta / .detailGrid). */
export function MetaGrid({ items }: { items: { label: string; value: React.ReactNode }[] }) {
  const shown = items.filter((item) => item.value !== undefined && item.value !== null && item.value !== "");
  if (shown.length === 0) return null;
  return (
    <div className={styles.metaGrid}>
      {shown.map((item) => (
        <div key={item.label}>
          <span>{item.label}</span>
          <strong>{item.value}</strong>
        </div>
      ))}
    </div>
  );
}
