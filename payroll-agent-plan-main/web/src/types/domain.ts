import type { QaSource } from "../api/qa";

export type Category = "qa" | "changelist" | "todo" | "out_of_scope";

export type Priority = 1 | 2 | 3 | 4 | 5;

export type HistoryStatus =
  | "done"
  | "accepted"
  | "discarded"
  | "approved"
  | "needs_clarification";

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

export interface HistoryItem {
  id: string;
  subject: string;
  status: HistoryStatus;
  category: Category;
  priority: Priority;
  receivedAt: string;
  clientId?: string;
  employeeId?: string;
  bodyExcerpt?: string;
  extracted?: Record<string, string>;
}

export interface DraftItem {
  id: string;
  subject: string;
  to: string;
  body: string;
  status: "pending" | "accepted" | "discarded" | "sent";
  relatedQueueId?: string;
}

export interface ChangeListItem {
  id: string;
  clientId: string;
  title: string;
  lines: {
    id: string;
    field: string;
    from?: string;
    to?: string;
    reviewed: boolean;
    effectiveDate?: string;
    incomplete?: boolean;
    recommendedSystem?: string;
    recommendedField?: string;
  }[];
  dueDate?: string;
  status?: "pending" | "incomplete";
  priority?: Priority;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  /** @deprecated prefer toolSources for expandable panes */
  sources?: string[];
  toolSources?: QaSource[];
}
