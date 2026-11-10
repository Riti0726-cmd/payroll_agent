# Classifier, Extract & Full Triage Flow — Design Spec

**Date:** 2026-09-24  
**Status:** Implemented  
**Component focus:** Classifier & extract, plus triage orchestration (full graph per email, dedupe, thread)  
**Source requirements:** `Requirement/Engage AI - Payroll Specialist - Use Case - Copy.xlsx` (UC-011–020 primary; UC-001–010 as existing triage plumbing)  
**Related:** `docs/superpowers/specs/2026-09-23-payroll-specialist-ui-design.md`

## 1. Goal

When a specialist starts triage (`TRIAGE_RUN`), the engine must:

1. Fetch emails in the processing window  
2. **Skip already-processed** messages (dedupe)  
3. For each remaining message, resolve **thread context** and the **current request**  
4. Run the **full LangGraph** per email: classify → QA / drafting / routing by category  
5. Persist results and mark the message processed on success  

Standalone console Q&A (`POST /qa`) remains a **normal specialist chat agent** — no mailbox triage, no classifier required for ordinary chat turns.

## 2. Locked decisions

| Topic | Choice |
|---|---|
| Build style | Component-wise (not UC-by-UC tickets) |
| First backend component | Classifier & extract + triage flow wiring |
| Category taxonomy | Keep engine: `qa \| changelist \| todo \| out_of_scope` + `oos_destination` |
| Sheet taxonomy (Pay Change, Off Cycle, …) | Docs/UI mapping only — not the runtime enum |
| Extraction (R1) | Core fields: `employee_id`, `pay_period`, `client_id`, `employee_name`, `effective_date`, `intent` |
| Inventing fields | Never invent IDs/dates/names; missing → `null` |
| Triage processing model | **B — full LangGraph per unprocessed email** |
| Dedupe | Yes — skip already-processed by Message ID |
| Thread | Yes — Conversation ID, load prior messages, determine current request |
| Chat / Q&A | Separate normal agent (`POST /qa`); out of this component’s behavior change |
| UC-017 business rules engine | Deferred — prompt + structured schema only this phase |

## 3. Architecture

```text
TRIAGE_RUN specialist_id=…
  │
  ├─ load specialist config (lookback, mode, interval)
  ├─ create run_id
  ├─ compute processing window
  ├─ Graph: list messages in window (subject, body, conversationId, …)
  │
  ├─ for each message:
  │     ├─ if Message ID already processed → skip (dedupe)
  │     ├─ resolve Conversation ID
  │     ├─ load prior thread messages (capped)
  │     ├─ determine current request text (latest actionable + light history strip)
  │     ├─ LangGraph.ainvoke({ inquiry: current_request, metadata… })
  │     │     intake → classifier → qa_specialist | drafting | routing
  │     ├─ persist classification + extracts + draft/findings
  │     └─ mark Message ID processed (only on success)
  │
  └─ complete run + triage summary
```

```text
POST /qa  ──► standalone Q&A agent (Cortex) ──► { answer, sources }
              (unchanged; not part of mailbox triage)
```

### Why full graph per email (B)

Product expectation: starting triage runs the **whole specialist pipeline** for each new mail (classify, then category-specific work), not classify-only. Shared nodes already exist in `graph.py`; triage becomes the batch driver that invokes that graph once per unprocessed email.

### Cost / limits

- N unprocessed emails ⇒ N graph runs (tokens + latency).  
- Dedupe keeps repeat runs cheap.  
- Thread fetch is capped (see §5).  
- Optional later: concurrency limit / batching — not required for R1 if lookback windows stay small.

## 4. Data model

### 4.1 `ClassificationResult` (extend)

Keep existing:

- `category`, `intent`, `confidence`  
- `employee_id`, `pay_period`  
- `oos_destination` (`benefits` | `tax` | `workers_comp` | `other` | null)

Add Core R1:

- `client_id: str | None`  
- `employee_name: str | None`  
- `effective_date: str | None` (ISO date string when explicit; else null)

`intent` remains the short request summary.

### 4.2 Taxonomy mapping (documentation only)

| Sheet label (UC-016) | Engine category |
|---|---|
| Q&A | `qa` |
| Pay Change Request | `changelist` |
| Pay Approval | `todo` |
| Off Cycle | `todo` |
| Internal Routing (payroll ops handoff) | `todo` |
| Benefits / Tax / Workers’ Comp | `out_of_scope` (+ `oos_destination`) |
| Others | `todo` unless clearly non-payroll → `out_of_scope` |

Runtime enum does **not** change. Queue UI continues to filter on engine categories.

### 4.3 Processed-mail store

Use existing Neon `EmailRepository` / `email_processing` where available:

- Upsert on ingest with `message_id`, `conversation_id`, subject/body  
- `is_processed` / `mark_processed` after successful graph completion  
- Fallback: triage store (blob/local) processed-ID set if Neon unavailable in an environment — same Message ID semantics  

## 5. Dedupe & thread (both in scope)

### 5.1 Dedupe (UC-011)

| Rule | Behavior |
|---|---|
| Key | Immutable Outlook **Message ID** |
| Skip | Message ID already marked processed |
| Process | New Message ID (including follow-ups in an old conversation) |
| Failure | Do **not** mark processed; next run retries |
| Not sufficient alone | Outlook “read” flag — processing state is authoritative |

### 5.2 Thread (UC-012–014)

| Step | Behavior |
|---|---|
| Identify | Prefer Graph `conversationId`; fallback only if absent (e.g. treat as single-message thread) |
| Retrieve chain | Load prior messages for that conversation (same mailbox), newest-last, **cap** (e.g. 10 messages or ~token budget) |
| Current request | Prefer latest message body as primary; attach short prior context; strip signatures/quoted blobs where practical |
| Cross-client | Do not merge threads across mailboxes; stay within specialist mailbox |

Graph mailbox port must return `conversation_id` and enough body text for classify (prefer full body over preview when available).

## 6. Classifier & extract behavior

- Structured LLM output → `ClassificationResult` (same schema for graph classifier node).  
- Prompt: engine taxonomy + Core R1 fields + never invent.  
- Keyword heuristics: **fallback only** when LLM unavailable (offline tests / missing key), not the primary triage path.  
- OOS: set `oos_destination`; routing node drafts **internal** note (no external send, no Snowflake for OOS).  
- QA category: existing QA node + Cortex tools.  
- Changelist / todo: drafting node produces reviewable draft (HITL send remains later UI).  

UC-017 (versioned business-rule table): **out of scope** this phase; document as follow-up when Business Rules sheet is filled.

## 7. Error handling

| Case | Behavior |
|---|---|
| Graph fetch failure | Fail run; no partial “succeeded” window advance unless policy already records partial — prefer fail closed on retrieve |
| Single email graph failure | Log; leave unprocessed; continue other emails; include failure in summary |
| Missing both client_id and employee_id | Still classify; downstream may draft clarification later (GR-010 full enforcement can land with drafting HITL) — classifier must not invent IDs |
| Empty window / all skipped | Succeeded run with zero processed emails |

## 8. Telemetry & PII

- Keep step spans: `retrieve_emails`, `dedupe_skip`, `thread_load`, `process_email`, `classifier`, category nodes, `finalize_run`.  
- Attributes: `run_id`, `specialist_id`, `message_id`, `conversation_id`, `category`, `skipped`, `status`.  
- Do **not** put full subject/body/names into span attributes (existing PII guard).

## 9. Testing

- Unit: `ClassificationResult` schema (new fields optional/null).  
- Unit: dedupe skip vs new Message ID in same conversation.  
- Unit: thread cap + current-request assembly.  
- Integration (mock mailbox + mock LLM): TRIAGE_RUN processes 2 new mails with full graph path; second run skips them.  
- Offline: heuristic fallback still returns valid category dict when no API key.

## 10. Success criteria

- `TRIAGE_RUN` skips processed Message IDs.  
- Unprocessed emails get Conversation ID + capped thread context + current-request text.  
- Each unprocessed email runs full graph; results include category, Core R1 extracts, and category branch output (findings/draft/routing note).  
- Successful emails marked processed; failures retryable.  
- `POST /qa` behavior unchanged as normal chat agent.  
- Engine taxonomy unchanged; sheet mapping documented.  

## 11. Non-goals (this phase)

- Changing chat into a classifier.  
- FastAPI BFF.  
- Autonomous send or PRISMHR/iSolved write-back.  
- Full UC-020 field set (rates, amounts, position).  
- Versioned Business Rules engine (UC-017/019 tables).  
- Queue/Drafts UI polish (consume persisted results in a later component).  
- Learning from edits (UC-028/064).

## 12. Suggested implementation order (for plan)

1. Extend `ClassificationResult` + classifier prompts.  
2. Mailbox: `conversation_id` + body; repository wire for processed + thread.  
3. Orchestrator: dedupe → thread → current request → `graph.ainvoke` per email → mark processed.  
4. Inject real LLM classify into graph (heuristic fallback for tests).  
5. Tests + short taxonomy mapping note in README or `docs/`.  
