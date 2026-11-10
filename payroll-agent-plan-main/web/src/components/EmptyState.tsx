import styles from "./EmptyState.module.css";

const DEFAULT_TITLE = "Not connected yet";
const DEFAULT_DETAIL =
  "This area is ready in the UI, but backend wiring is still pending. Data will appear here once the agent connection is configured.";

type EmptyStateProps = {
  title?: string;
  detail?: string;
};

export function EmptyState({
  title = DEFAULT_TITLE,
  detail = DEFAULT_DETAIL,
}: EmptyStateProps) {
  return (
    <section aria-labelledby="empty-state-title" className={styles.empty} data-enter>
      <h2 className={styles.title} id="empty-state-title">
        {title}
      </h2>
      <p className={styles.detail}>{detail}</p>
    </section>
  );
}
