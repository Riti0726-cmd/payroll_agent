import type { QueueItem } from "../types/domain";

export function sortQueueItems(items: QueueItem[]): QueueItem[] {
  return [...items].sort((a, b) => {
    if (a.priority !== b.priority) return a.priority - b.priority;
    return a.receivedAt.localeCompare(b.receivedAt);
  });
}
