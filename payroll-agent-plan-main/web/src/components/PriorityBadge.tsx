import type { Priority } from "../types/domain";

type PriorityBadgeProps = {
  priority: Priority;
};

export function PriorityBadge({ priority }: PriorityBadgeProps) {
  const isHighPriority = priority <= 2;

  return (
    <span
      aria-label={`Priority ${priority}`}
      style={{
        background: isHighPriority ? "var(--amber-wash)" : "var(--paper-2)",
        border: `1px solid ${isHighPriority ? "var(--amber-ring)" : "var(--line)"}`,
        borderRadius: "var(--radius)",
        color: isHighPriority ? "var(--amber-dim)" : "var(--muted)",
        display: "inline-flex",
        fontFamily: "var(--font-display)",
        fontSize: "0.6875rem",
        fontWeight: isHighPriority ? 800 : 600,
        letterSpacing: "0.06em",
        lineHeight: 1,
        padding: "0.3125rem 0.4375rem",
        textTransform: "uppercase",
      }}
    >
      P{priority}
    </span>
  );
}
