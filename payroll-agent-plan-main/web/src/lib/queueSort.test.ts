import { describe, it, expect } from "vitest";
import { sortQueueItems } from "./queueSort";
import type { QueueItem } from "../types/domain";

const base = (over: Partial<QueueItem>): QueueItem => ({
  id: "1",
  subject: "s",
  category: "todo",
  priority: 3,
  receivedAt: "2026-09-23T10:00:00Z",
  ...over,
});

describe("sortQueueItems", () => {
  it("orders by priority then receivedAt", () => {
    const items = [
      base({ id: "a", priority: 3, receivedAt: "2026-09-23T12:00:00Z" }),
      base({ id: "b", priority: 1, receivedAt: "2026-09-23T11:00:00Z" }),
      base({ id: "c", priority: 1, receivedAt: "2026-09-23T09:00:00Z" }),
    ];
    expect(sortQueueItems(items).map((i) => i.id)).toEqual(["c", "b", "a"]);
  });
});
