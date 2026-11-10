# Live triage progress (SSE) — design

**Date:** 2026-09-26  
**Status:** Approved for implementation (approach 1)

## Goal

Show a live header indicator while triage processes each mailbox email (n/total + subject/category).

## Approach

- `POST /triage/stream` on the specialist host returns SSE events.
- `TriageOrchestrator.run(..., on_progress=...)` emits per-email events.
- Workbench "Run triage" uses the stream (Graph Bearer), not Foundry blocking invoke.
- Foundry `TRIAGE_RUN` remains for scheduled/hosted agents (no live UI there).

## Events

- `run_started` — `{ runId, mailbox, total }`
- `email_started` — `{ index, total, messageId, subject }`
- `email_finished` — `{ index, total, messageId, subject, status, category?, error? }`
- `run_finished` — `{ runId, succeeded, failed, skipped, summary }`
- `error` — `{ message }`

## UI

- Header pill beside Run triage (AppShell), shared via triage run context so Settings uses the same run.
- Toast still used for token/start/complete/fail copy.
