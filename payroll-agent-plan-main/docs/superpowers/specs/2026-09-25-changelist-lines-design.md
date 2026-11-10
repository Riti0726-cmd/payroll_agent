# Change-list lines — map `changes` + preserve on triage

**Date:** 2026-09-25  
**Status:** Implemented  
**Branch:** `main`  
**Parent:** `docs/superpowers/specs/2026-09-25-workbench-connectivity-design.md`

## 1. Goal

Show real change-list line details in the workbench when Neon already has them, and stop triage from overwriting rich `changelist_response` payloads with an empty shell.

## 2. Decision

**Approach C**

| Piece | Change |
|---|---|
| A — Map on read | `row_to_changelist_item` maps `changelist_response.changes` → UI `lines` when `lines` is missing/empty |
| B — Write on triage | Persist merges into existing JSON; never replace a payload that already has `changes` or non-empty `lines` with `{ lines: [] }` |

Out of scope: Snowflake lookups, new LLM extractors, UI redesign, Approve/clarification behavior, inventing from/to when neither `lines` nor `changes` exist.

## 3. Neon shapes

### UI / shell shape (already supported)

```json
{
  "clientId": "12890",
  "title": "Regarding change in hourly rate",
  "lines": [
    { "id": "l0", "field": "hourly_pay_rate", "from": "20.0", "to": "22.0", "reviewed": false }
  ],
  "status": "pending"
}
```

### Agent / rich shape (already in Neon)

```json
{
  "agent": "changelist",
  "intent": "salary_change",
  "parameters": { "client_id": "12890", "employee_id": "10452", ... },
  "changes": [
    { "field": "hourly_pay_rate", "from": 20.0, "to": 22.0, "effective_date": "2026-09-14", "notes": "..." }
  ],
  "status": "ready"
}
```

## 4. Read path (A)

In `changelists_mapping.row_to_changelist_item`:

1. Parse `changelist_response` JSON as today.
2. **Lines source**
   - If `payload.lines` is a non-empty list → map those (existing behavior).
   - Else if `payload.changes` is a non-empty list → map each change to a UI line.
   - Else → `lines: []`.
3. **Change → line mapping**

   | Source | Target |
   |---|---|
   | `field` | `field` (string; empty string if missing) |
   | `from` | `from` — stringify numbers/bools; omit/`null` stays null (UI shows Empty) |
   | `to` | `to` — same |
   | — | `id` = existing `id` or `l{index}` |
   | — | `reviewed` = bool from source or `false` |

4. **clientId** precedence: `payload.clientId` → `payload.parameters.client_id` → extracts `client_id` → `"unknown"`.
5. **title** precedence: `payload.title` → row `subject` → `"(no subject)"`.

No HTTP / frontend changes required; `ChangeListsPage` already renders lines.

## 5. Write path (B)

In `TriageOrchestrator._persist_workbench_payloads` when `category == "changelist"`:

1. Load existing `changelist_response` for `message_id` if the repo exposes it; if not available cheaply, treat as missing (shell-only write is OK for brand-new rows).
2. Build a **shell** `{ clientId, title, lines: [], status: "pending" }` from triage + subject (same fields as today).
3. **Merge rules**
   - If existing payload has non-empty `changes` **or** non-empty `lines` → keep that payload; only fill missing `clientId` / `title` / `status` from the shell when absent.
   - Else → save the shell (may still have empty `lines` when triage has no change facts).
4. Do **not** invent rate/bank lines from free text in this slice.
5. Update `test_triage_workbench_persist` (and add a merge case) so empty-shell overwrite of rich `changes` is forbidden.

Optional repo helper (if needed): `get_changelist_response(message_id) -> dict | None` — only if merge cannot be done without a read.

## 6. Tests

| Test | Assert |
|---|---|
| Mapper: `changes` only | UI lines populated; `from`/`to` stringified |
| Mapper: non-empty `lines` wins over `changes` | Uses `lines` |
| Mapper: `parameters.client_id` | `clientId` set |
| Mapper: empty both | `lines: []` |
| Triage: first changelist | Shell with `lines: []` still OK |
| Triage: existing rich `changes` | Re-persist keeps `changes`; does not write empty `lines` over them |

## 7. Success criteria

- Pending Neon changelist rows with `changes` show field/from/to in Change lists detail.
- Re-running triage does not wipe those `changes`.
- Approve / Request clarification unchanged.
- Existing unit tests updated; web UI tests unchanged unless copy tweaks.

## 8. Non-goals

- Backfilling or rewriting historical JSON in place via migration SQL.
- Showing `effective_date` / `notes` as separate UI columns (may appear only if later folded into `field` label — not required now).
- Snowflake validation of from/to values.
