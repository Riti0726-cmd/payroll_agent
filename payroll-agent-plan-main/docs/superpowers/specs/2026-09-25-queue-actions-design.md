# Queue Actions Design

**Date:** 2026-09-25  
**Status:** Approved for implementation  

## Scope

| Action | Behavior |
|---|---|
| Mark done | `is_processed=true`, `hitl_status=done`; drops off open Queue |
| Adjust priority | Persist `priority_rate` from UI P1–P5 (`1→high`, `2\|3\|4→medium`, `5→low`) |
| Open draft | Navigate to `/drafts?id={messageId}` when a draft exists; else toast |

## API

`PATCH /queue/{message_id}?specialist_id=…` (+ optional `mailbox=`)

Body (at least one field):
```json
{ "done": true }
{ "priority": 1 }
{ "done": true, "priority": 3 }
```

Response: updated `QueueItem` JSON (or 404 if missing).

## Out of scope

- Email Send from Queue  
- Learning from priority edits (UC-028)
