# Queue UI — Neon Wiring Design

**Date:** 2026-09-25  
**Status:** Approved for planning  
**Parent:** `docs/superpowers/specs/2026-09-23-payroll-specialist-ui-design.md`  
**Requirements:** UC-026 (primary); UC-027/028 deferred  
**Slice:** Queue list + detail only (actions remain “Not connected yet”)

## 1. Goal

Populate the Queue workbench from Neon `email_processing` after triage, with no blob or Graph fallback for the list API.

## 2. Decisions (locked)

| Topic | Choice |
|---|---|
| Queue source of truth | Neon `email_processing` only |
| Blob / local triage runs | Audit / lookback only — **not** read by Queue UI |
| Fallback when DB unavailable | None — return error; UI shows error + retry |
| HTTP surface | Starlette `GET /queue` on Responses host (same pattern as `POST /qa`) |
| Scope | List + detail + client filters; no Mark done / Adjust priority / Open draft persist |
| Priority model | DB: `low\|medium\|high` → UI: P5 / P3 / P1 (fixed map until UC-025 scoring lands) |

## 3. Architecture

```text
Outlook (Graph)
    │  TRIAGE_RUN
    ▼
TriageOrchestrator
    ├── upsert_ingested_email  → Neon email_processing
    ├── save_classification    → category + priority_rate (+ extracts when available)
    ├── optional draft / qa / changelist payloads on the row
    └── complete_run           → blob/local run JSON (audit; UI ignores)

Queue UI
    └── GET /queue?specialist_id=…  → EmailRepository list open categorized rows
            └── map → QueueItem[]
```

- No FastAPI BFF.
- No reading triage run JSON for the queue.
- No re-fetch from Graph on queue page load.

## 4. Data rules

### 4.1 Which rows appear in Queue

- `is_categorized = true`
- `is_processed = false`
- Scoped to the specialist (match `payroll_specialist_email` / configured mailbox for that specialist)
- Ordered by mapped priority (P1 first), then `email_received_dttm` descending

### 4.2 Triage write path

On each **succeeded** classified email during `TRIAGE_RUN`:

1. `upsert_ingested_email` with Graph fields (message_id, sender, subject, body, conversation_id, received_at, specialist mailbox as recipient).
2. `save_classification` with category (`qa` | `changelist` | `todo` | `out_of_scope`) and `priority_rate` (`low` | `medium` | `high`; default `medium` until real scoring).
3. Persist extract fields used by detail when available (`client_id`, `employee_id`, etc.) — prefer existing columns / compact JSON already used by the pipeline; do not invent a second store.

Skipped / failed emails: do not open a categorized queue row. If Neon write fails for an email, log the error and mark that result `status: failed` in the triage run record (do not silently skip the DB write).

### 4.3 Row → `QueueItem` mapping

| UI field | Source |
|---|---|
| `id` | `message_id` |
| `subject` | `subject`, or `"(no subject)"` |
| `category` | First allowed token from `category` CSV |
| `priority` | `high`→1, `medium`→3, `low`→5; missing → 3 |
| `receivedAt` | `email_received_dttm` ISO-8601 |
| `clientId` / `employeeId` | From persisted extracts when present |
| `bodyExcerpt` | First ~280 chars of `content` |
| `extracted` | Structured extracts when present |

## 5. API

### `GET /queue?specialist_id={id}`

| Case | Response |
|---|---|
| Success | `200` `{ "items": QueueItem[] }` |
| Missing `specialist_id` | `400` `{ "detail": "..." }` |
| No `DATABASE_URL` / DB unavailable | `503` `{ "detail": "..." }` — **no fallback** |

Auth: Bearer token (same as Q&A). Specialist id from query for this slice (claims wiring can follow later).

Mount on Responses host via a small module parallel to `qa_http.py` (e.g. `queue_http.py`).

## 6. Frontend

- Env: `VITE_QUEUE_URL` (local default `/api/queue`).
- Vite proxy: `/api/queue` → `http://127.0.0.1:8088/queue`.
- Client: `web/src/api/queue.ts` — fetch with access token; typed errors.
- `QueuePage`: loading → populated list/detail; empty success → existing empty copy; error → inline error + retry.
- Category / priority filters remain client-side.
- Actions (Open draft, Mark done, Adjust priority) stay toast “Not connected yet”.

## 7. Testing

- **Mapping unit test (required):** Neon-shaped row / DTO → `QueueItem` — category CSV, priority map, subject/receivedAt/bodyExcerpt fallbacks. Keep this test; do not leave mapping untested.
- Handler tests: empty list, happy path, 400 missing specialist, 503 without DB.
- Frontend: queue client request shaping; QueuePage loading / empty / error smoke as appropriate.

## 8. Out of scope

- Mark done / Adjust priority / Open draft persistence (UC-027)
- Learning from queue edits (UC-028)
- Blob or Graph fallback for queue reads
- Schema migration beyond using existing `email_processing`
- FastAPI BFF; streaming
- Full UC-025 priority scoring (use fixed low/medium/high map)

## 9. Success criteria

- With `DATABASE_URL` set, a successful triage run that categorizes emails yields those open items in Queue list + detail.
- Without DB, Queue shows a clear error and no fake rows.
- Mapping is covered by an automated unit test.
- Visual shell and filters behave as today once items load.
