# Workbench Connectivity — Settings, Drafts, Change Lists

**Date:** 2026-09-25  
**Status:** Approved for planning  
**Parent:** `docs/superpowers/specs/2026-09-23-payroll-specialist-ui-design.md`  
**Related:** `docs/superpowers/specs/2026-09-25-queue-neon-wiring-design.md`  
**Slice:** Connectivity only — list/detail + HITL status writes; no Snowflake; no Graph Send

## 1. Goal

Wire Settings, Drafts, and Change lists to the existing Python Responses host and Neon / triage store, using the same pattern as Queue (`GET /queue`).

Focus is **connectivity** (UI ↔ API ↔ store), not inventing changelist line population or payroll facts.

## 2. Decisions (locked)

| Topic | Choice |
|---|---|
| Architecture | Approach A — Starlette routes on Responses host (mirror Queue / Q&A) |
| Snowflake | Out of scope — do not touch Cortex MCP / QA tool path |
| Graph Send | Out of scope — Draft **Send** stays toast “Not connected yet” |
| Population | Do not invent rich changelist field/from/to extractors |
| HITL writes | Drafts: Accept / Discard; Change lists: Approve / Request clarification |
| Settings | Load + save lookback / mode / interval; show run history from triage store |
| Missing DB | Drafts / Change lists → HTTP 503 (same as Queue); Settings config may use local/blob store without Neon |
| FastAPI BFF | No |
| Auth | Bearer optional (same as Queue / Q&A); `specialist_id` query for this slice |

## 3. Architecture

```text
Browser (web/)
  ├── SettingsPage  → VITE_SETTINGS_URL  → GET/PUT /settings
  ├── DraftsPage    → VITE_DRAFTS_URL    → GET /drafts, PATCH /drafts/{id}
  └── ChangeLists   → VITE_CHANGELISTS_URL → GET /changelists, PATCH /changelists/{id}

Responses host (:8088)
  ├── triage store (local/blob) — specialist config + run JSON
  └── Neon email_processing     — drafts + changelist rows + hitl_status
```

Vite proxies (local):

- `/api/settings` → `http://127.0.0.1:8088/settings`
- `/api/drafts` → `http://127.0.0.1:8088/drafts`
- `/api/changelists` → `http://127.0.0.1:8088/changelists`

## 4. Data rules

### 4.1 HITL status column

Add nullable text column on `email_processing`:

- `hitl_status TEXT NULL`

Allowed values (by surface):

| Surface | Values |
|---|---|
| Drafts | `pending` (default when drafted), `accepted`, `discarded` |
| Change lists | `pending` (default when changelist row opened), `approved`, `needs_clarification` |

`sent` is reserved for a later Graph Send slice — not set by this work.

Do **not** overload `is_processed` alone to mean Accept vs Discard (those must remain distinguishable).

Accept / Discard / Approve / Request clarification update `hitl_status` only (plus optional draft body edit on Accept path if the UI sends an edited body). They do **not** send mail.

### 4.2 Which rows appear in Drafts

- `is_drafted = true`
- `draft_content` is non-null
- `hitl_status` is null or `pending`
- Scoped to specialist mailbox (same mailbox match as Queue)
- Ordered by `mail_draft_time` desc (fallback `email_received_dttm` desc)

### 4.3 Which rows appear in Change lists

- Category CSV includes `changelist` (first/allowed token)
- `hitl_status` is null or `pending`
- Scoped to specialist mailbox
- Ordered by `email_received_dttm` desc

Detail mapping (connectivity, not rich extraction):

| UI field | Source |
|---|---|
| `id` | `message_id` |
| `clientId` | extract `client_id` from `sub_content` JSON, else `"unknown"` |
| `title` | `subject` or `"(no subject)"` |
| `lines` | Parse `changelist_response` JSON `lines` if present and well-formed; else `[]` |

No new LLM step to invent lines.

### 4.4 Draft item mapping

| UI field | Source |
|---|---|
| `id` | `message_id` |
| `subject` | `subject` or `"(no subject)"` |
| `to` | `sender_email` (reply target for display) |
| `body` | `draft_content` |
| `status` | map `hitl_status` → UI (`pending` default) |
| `relatedQueueId` | same `message_id` |

### 4.5 Triage persist (connectivity)

On each succeeded email after Neon queue persist, if payloads already exist from `process_email_fn`:

1. If `draft` is a non-empty string → `save_draft` and set `hitl_status = pending`.
2. If category is `changelist` → `save_changelist_response` with a minimal JSON shell when none exists:

```json
{
  "clientId": "<extract or unknown>",
  "title": "<subject or no subject>",
  "lines": [],
  "status": "pending"
}
```

If `changelist_response` already has content, do not overwrite blindly — only ensure `hitl_status` is `pending` when newly categorized. Prefer merge: keep existing JSON; set status pending if missing.

QA-category drafts that depend on Snowflake findings: if the email graph returns no draft (or empty), skip draft persist — do not invent content.

### 4.6 Settings

Backed by existing triage store (`get_specialist_config` / `save_specialist_config` / `list_runs`):

| Field | Store key |
|---|---|
| lookback days | `lookback_days` |
| mode | `mode` (`manual` \| `recurring`) |
| interval | `interval_hours` (`2` \| `4` \| `24`) |
| run history | `list_runs` → started / status / summary snippet |

Settings does **not** require Neon. Missing store still returns defaults via existing store behavior.

## 5. API

### Settings

`GET /settings?specialist_id={id}` → `200`

```json
{
  "lookbackDays": 7,
  "mode": "manual",
  "intervalHours": 2,
  "runs": [
    { "runId": "...", "startedAt": "...", "status": "succeeded", "result": "..." }
  ]
}
```

`PUT /settings?specialist_id={id}` body:

```json
{ "lookbackDays": 7, "mode": "manual", "intervalHours": 2 }
```

→ `200` with saved config (same shape, `runs` optional/refreshed).

| Case | Response |
|---|---|
| Missing `specialist_id` | `400` |
| Invalid interval/mode | `400` |

### Drafts

`GET /drafts?specialist_id={id}` → `200` `{ "items": DraftItem[] }`

`PATCH /drafts/{message_id}?specialist_id={id}` body:

```json
{ "status": "accepted" | "discarded", "body": "<optional edited draft>" }
```

→ `200` updated item; `404` if missing; `503` if no DB.

### Change lists

`GET /changelists?specialist_id={id}` → `200` `{ "items": ChangeListItem[] }`

`PATCH /changelists/{message_id}?specialist_id={id}` body:

```json
{ "status": "approved" | "needs_clarification" }
```

→ `200` updated item; `404` / `503` as above.

Mount as three modules parallel to `queue_http.py`: `settings_http.py`, `drafts_http.py`, `changelists_http.py`.

## 6. Frontend

| Env | Local default |
|---|---|
| `VITE_SETTINGS_URL` | `/api/settings` |
| `VITE_DRAFTS_URL` | `/api/drafts` |
| `VITE_CHANGELISTS_URL` | `/api/changelists` |

- Clients: `web/src/api/settings.ts`, `drafts.ts`, `changelists.ts` — same error style as `queue.ts`.
- `SettingsPage`: load on mount; explicit **Save configuration** button (PUT); Run triage unchanged; run history table from GET.
- `DraftsPage` / `ChangeListsPage`: loading / error+retry / empty / populated; Accept/Discard and Approve/Request clarification call PATCH; **Send** remains toast.
- Update `web/README.md` wiring table.

## 7. Testing

- Mapping unit tests: Neon row → DraftItem / ChangeListItem (including empty `lines`).
- Handler tests: 400 / 200 / 503 / 404; PATCH status updates.
- Settings handler tests: GET defaults, PUT validation.
- Triage persist test: draft string → `save_draft`; changelist category → `save_changelist_response` shell.
- Frontend client tests: URL + Authorization + error class (mirror `queue.test.ts`).

## 8. Out of scope

- Snowflake / Cortex MCP changes
- Graph Send / Outlook write-back
- Rich changelist line extraction
- Queue Mark done / Adjust priority / Open draft navigation polish beyond existing toast
- Learning-from-edits (UC-028 / UC-064)
- FastAPI BFF; streaming

## 9. Success criteria

- With Neon + triage producing drafts, Drafts list shows them; Accept/Discard persist and remove from pending list.
- With Neon changelist-categorized rows, Change lists shows them (possibly with `lines: []`); Approve / Request clarification persist.
- Settings load/save updates specialist config used by next `TRIAGE_RUN`; run history lists recent runs.
- Without Neon, Drafts/Change lists show clear error (503 path); Settings still works via triage store.
- Send remains explicitly not connected.

## 10. Non-goals

- Populating realistic changelist line items
- End-to-end mail delivery
- Replacing Queue or Q&A wiring
