# History Page Design

**Date:** 2026-09-25  
**Status:** Approved for implementation  

## Goal

Read-only History workbench area listing closed HITL emails from Neon.

## Decisions

| Topic | Choice |
|---|---|
| Surface | New nav **History** |
| Statuses | `done`, `accepted`, `discarded`, `approved`, `needs_clarification` |
| Filter | Client + optional `status` query (`all` or one status) |
| Mailbox | Same override as Queue (`mailbox=` / `VITE_QUEUE_MAILBOX`) |
| Actions | None (read-only) |

## API

`GET /history?specialist_id=…&mailbox=…&status=all|done|…`

Response: `{ "items": HistoryItem[] }` with id, subject, status, category, receivedAt, bodyExcerpt, extracted, clientId, employeeId.

## UI

Master–detail + status filter; empty/loading/error like Queue.
