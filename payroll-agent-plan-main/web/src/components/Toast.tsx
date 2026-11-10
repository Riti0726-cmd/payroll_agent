type ToastProps = {
  message: string | null;
  onDismiss: () => void;
};

export function Toast({ message, onDismiss }: ToastProps) {
  if (!message) {
    return null;
  }

  return (
    <div
      aria-live="polite"
      role="status"
      style={{
        alignItems: "center",
        background: "var(--ink-elevated)",
        border: "1px solid var(--amber-ring)",
        bottom: "1.25rem",
        boxShadow: "var(--shadow-panel)",
        color: "var(--fg)",
        display: "flex",
        gap: "0.75rem",
        padding: "0.75rem 0.875rem",
        position: "fixed",
        right: "1.25rem",
        zIndex: 20,
      }}
    >
      <span>{message}</span>
      <button type="button" onClick={onDismiss}>
        Dismiss
      </button>
    </div>
  );
}
