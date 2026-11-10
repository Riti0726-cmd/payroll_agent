import type { Category } from "../types/domain";

const categoryLabels: Record<Category, string> = {
  qa: "Q&A",
  changelist: "Change list",
  todo: "Todo",
  out_of_scope: "Out of scope",
};

type CategoryChipProps = {
  category: Category;
};

export function CategoryChip({ category }: CategoryChipProps) {
  return (
    <span
      style={{
        background: "var(--ink-elevated)",
        border: "1px solid var(--panel-border)",
        borderRadius: "var(--radius)",
        color: "var(--fg)",
        display: "inline-flex",
        fontSize: "0.6875rem",
        fontWeight: 600,
        letterSpacing: "0.04em",
        lineHeight: 1,
        padding: "0.3125rem 0.5rem",
        textTransform: "uppercase",
      }}
    >
      {categoryLabels[category]}
    </span>
  );
}
