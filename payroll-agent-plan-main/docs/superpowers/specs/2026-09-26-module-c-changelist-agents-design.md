# Module C Changelist Agents (Full B) — Design Spec

**Date:** 2026-09-26  
**Status:** Approved for implementation  
**Approach:** Full B — validation + changelist agent + due date/priority + HITL line edit  
**Source UCs:** UC-020, 021, 022/024/025, 034–036, 041, 055–063 (UC-059 no write-back)

## 1. Goal

When triage classifies mail as a pay-change (`changelist`), the email graph must validate client/employee against Snowflake, build a structured change list with field lines (from Cortex + email), set due date/priority, draft from facts, and support HITL edit/approve — without writing to PRISMHR/iSolved.

## 2. Graph shape

```text
START → classifier
  → validation_agent   (qa | changelist | todo; skip for out_of_scope)
       ├─ needs_clarification | invalid → drafting → END
       ├─ qa → qa_specialist → drafting → END
       ├─ changelist → changelist_agent → due_date_priority → drafting → END
       ├─ todo → drafting → END
       └─ out_of_scope → routing_agent → END
```

Standalone `POST /qa` unchanged (share MCP tool loading only).

## 3. Data

### Classifier extensions

`change_type`, `new_value`, `previous_value`, `system_target` — email-stated only; never invent.

### Validation

`status`: `ok` | `needs_clarification` | `invalid`; missing fields; notes; optional Snowflake refs.

### Neon `changelist_response`

Rich agent shape with `changes[]`, `due_date`, `due_date_source`, `priority_rate`, `parameters`, `sources`, `status` (`pending` | `incomplete`). UI maps `changes` → `lines`.

### PATCH `/changelists/{id}`

Accept `status` and/or `lines` edits. Approve allowed even if incomplete (UI warns). No write-back APIs.

## 4. Principles

- Never invent IDs, rates, or current (`from`) values.
- **Triage QA specialist and changelist agent require a live Snowflake MCP tool fetch.** No tools, stub-only (`snowflake_mcp_unavailable`), skipped tool calls, or failed tool results → blocked findings / empty `changes` (`snowflake_fetched=false`). Do not build email-only change lines.
- MCP failure → clarification / incomplete, not fake data.
- UC-059: recommendations only.
- Keep merge guard: never overwrite rich `changes` with empty shell.

## 5. Build order

1. Classifier enrich + models + changelist agent + persist  
2. Validation + clarification routing  
3. Due date + priority  
4. UI edit + PATCH lines  

## 6. Non-goals

UC-064 learning; Graph Send; UC-017 full rules engine; guaranteeing all Cortex views exist day one.
