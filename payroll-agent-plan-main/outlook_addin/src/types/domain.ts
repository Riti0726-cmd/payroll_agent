// Copied from web/src/types/domain.ts (source of truth) plus add-in-only EmailRecord.

export type Category = "qa" | "changelist" | "todo" | "out_of_scope";

export type Priority = 1 | 2 | 3 | 4 | 5;

export interface QueueItem {
  id: string;
  subject: string;
  category: Category;
  priority: Priority;
  receivedAt: string;
  clientId?: string;
  employeeId?: string;
  bodyExcerpt?: string;
  extracted?: Record<string, string>;
  hasDraft?: boolean;
}

export interface DraftItem {
  id: string;
  subject: string;
  to: string;
  body: string;
  status: "pending" | "accepted" | "discarded" | "sent";
  relatedQueueId?: string;
}

export interface ChangeListLine {
  id: string;
  field: string;
  from?: string;
  to?: string;
  reviewed: boolean;
  effectiveDate?: string;
  incomplete?: boolean;
  recommendedSystem?: string;
  recommendedField?: string;
}

export interface ChangeListItem {
  id: string;
  clientId: string;
  title: string;
  lines: ChangeListLine[];
  dueDate?: string;
  status?: "pending" | "incomplete";
  priority?: Priority;
}

/** GET /emails/lookup — one email's triage state for the task pane. */
export interface EmailRecord {
  id: string;
  subject: string;
  triaged: boolean;
  category?: Category;
  priority: Priority;
  receivedAt: string;
  /** hitl_status: pending | accepted | discarded | approved | needs_clarification | done */
  status?: string;
  done: boolean;
  clientId?: string;
  employeeId?: string;
  extracted?: Record<string, string>;
  draft?: DraftItem;
  changeList?: ChangeListItem;
}

export const CATEGORY_LABELS: Record<Category, string> = {
  qa: "Q&A",
  changelist: "Change list",
  todo: "To-do",
  out_of_scope: "Out of scope",
};
