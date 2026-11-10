// Ports of web/src/components/{PriorityBadge,CategoryChip}.tsx plus the pages' status badge.
import * as React from "react";
import { CATEGORY_LABELS, type Category, type Priority } from "../../../types/domain";
import styles from "./ui.module.css";

export function PriorityBadge({ priority }: { priority: Priority }) {
  const high = priority <= 2;
  return (
    <span
      aria-label={`Priority ${priority}`}
      className={high ? `${styles.priority} ${styles.priorityHigh}` : styles.priority}
    >
      P{priority}
    </span>
  );
}

export function CategoryChip({ category }: { category: Category }) {
  return <span className={styles.chip}>{CATEGORY_LABELS[category]}</span>;
}

type Tone = "neutral" | "warn" | "ok" | "danger";

export function StatusBadge({ tone = "neutral", children }: { tone?: Tone; children: React.ReactNode }) {
  const toneClass =
    tone === "warn"
      ? styles.statusWarn
      : tone === "ok"
        ? styles.statusOk
        : tone === "danger"
          ? styles.statusDanger
          : "";
  return <span className={`${styles.status} ${toneClass}`}>{children}</span>;
}

export function formatStatus(status: string | undefined): string {
  return (status ?? "pending").replace(/_/g, " ");
}
