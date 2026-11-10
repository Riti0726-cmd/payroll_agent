# Standalone Q&A Agent — Design Spec

**Date:** 2026-09-24  
**Status:** Approved for planning  
**Source requirements:** UC-042–053 (on-demand Q&A, Cortex, sources, conversation context)  
**Related:** `docs/superpowers/specs/2026-09-23-payroll-specialist-ui-design.md` (UI shell; Q&A wiring updated by this spec)

## 1. Goal

Replace the Q&A console’s use of the email triage pipeline (intake → classifier → QA node → email drafter) with a **standalone Q&A agent** that has direct access to Snowflake Cortex MCP tools and returns specialist-facing answers with sources.

The email triage agent (`TRIAGE_RUN` / Foundry Responses host) stays unchanged.

## 2. Decisions (locked)

| Topic | Choice |
|---|---|
| Product shape | Standalone Q&A **agent** (not a triage graph node reuse) |
| Hosting | Same process as today’s backend; **separate HTTP endpoint** |
| Routing | Path selects the agent (`POST /qa`); no `mode` flag on the triage invoke URL |
| Conversation context | UI sends **full message history** each request |
| Response | Chat `answer` + structured `sources` (no email-draft framing) |
| Triage Cortex | Leave triage QA node as-is; **share MCP tool loading** only |
| Implementation style | ReAct-style tool loop (LLM ↔ MCP until final answer) |
| Out of scope (this slice) | Streaming, server-side session store, refactoring triage to call the new agent |

## 3. Architecture

```text
Browser QaPage
  └── POST /qa  { messages: [...] }  ──► Q&A agent (ReAct + Cortex MCP)
                                         └── { answer, sources }

Outlook / Run triage / Foundry invoke
  └── existing Responses host ──► triage agent (unchanged)
```

- **Q&A agent:** system instructions + tools from `get_qa_tools()` / `mcp_config.json` + tool loop → structured response.
- **Triage agent:** existing LangGraph path (classifier, drafting, routing, triage orchestration). Unchanged behavior and Foundry invoke contract.
- **Shared:** MCP config / `get_qa_tools()` cache only — not prompts, not the console agent’s HTTP contract.
- **Hosting detail:** Keep ResponsesHostServer for triage. **Default:** serve `POST /qa` from the same process (shared or adjacent ASGI app). **Fallback only if that is blocked:** thin sibling HTTP server on a documented port that only serves `/qa`.

## 4. Request / response contract

### Endpoint

`POST /qa`

**Auth:** Bearer token (same Entra pattern as current agent calls).

### Request

```json
{
  "messages": [
    { "role": "user", "content": "Why was August net pay lower for EMP-123?" },
    { "role": "assistant", "content": "..." },
    { "role": "user", "content": "Break out the deductions." }
  ]
}
```

- Full thread each call (UI-owned history).
- Roles for v1: `user` | `assistant` only.
- Empty or missing `messages` → `400`.

### Success response

```json
{
  "answer": "Net pay dropped mainly because...",
  "sources": [
    {
      "label": "Payroll structured facts",
      "detail": "Cortex Analyst tool / semantic view reference + key filters"
    }
  ]
}
```

- `answer`: natural language for the **Payroll Specialist / HRC** (third person about employees; not an employee email or “your paycheck” reply).
- `sources`: array; may be empty when tools fail or nothing is citable.
- Do not invent payroll numbers or fake sources.

### Error responses

| Status | When |
|---|---|
| `400` | Invalid body |
| `401` / `403` | Auth failure |
| `502` / `503` | Agent process / hard failure to run; response body includes short `detail` |

When the agent runs but MCP/tools fail: prefer `200` with an honest “cannot verify” `answer` and empty or error-noted `sources`.

## 5. Q&A agent behavior

1. Build chat context from `messages` plus QA system instructions (Cortex-first, no invented figures, name lookup when employee ID missing).
2. Bind MCP tools from `get_qa_tools()`.
3. Run a ReAct-style loop until the model returns a final answer (bounded max tool rounds for safety).
4. Derive `sources` from tools actually invoked / references returned — never fabricate citations.
5. Return `{ answer, sources }`.

**Audience:** the Payroll Specialist using the console — not the employee. Answers are investigative/operational for the specialist; do not draft employee-facing copy or address the employee as “you”.

**Explicit non-goals for this agent:** classification categories, out-of-scope routing notes, email draft headers (`Triaged Category`, etc.), employee-facing emails.

## 6. UI wiring

| Concern | Change |
|---|---|
| Client | New `invokeQaChat(messages, token)` targeting `VITE_QA_INVOKE_URL` |
| QaPage | On send: append user message → POST full history → append assistant bubble with `answer` + `sources` |
| UX kept | Enter-to-send, loading state, inline error + Retry without duplicating user bubble |
| Triage | Unchanged: `VITE_FOUNDRY_INVOKE_URL` + `TRIAGE_RUN` |
| Config | If `VITE_QA_INVOKE_URL` unset → clear config error; **do not** fall back to Foundry triage invoke |

Update `web/README.md` so Q&A maps to `/qa`, not “intake → classifier → QA → drafting”.

## 7. Error handling (UI + agent)

- Auth / network / 5xx: inline error + Retry.
- Missing QA URL: config message, no silent Foundry fallback.
- Tool/MCP unavailable: honest answer, no invented numbers.

## 8. Testing

- **Unit:** request validation; response parse (`answer` + `sources`); with MCP stubbed unavailable, agent returns honest cannot-verify content.
- **Manual:** multi-turn follow-up in Q&A; sources panel when present; Run triage still works on Foundry URL; Q&A path never returns classifier JSON or email-draft headers as the primary answer.

## 9. Success criteria

- Q&A console uses only `POST /qa` and the standalone MCP-backed agent.
- Responses are chat answers with optional structured sources.
- Triage / Outlook / `TRIAGE_RUN` behavior and Foundry invoke contract remain unchanged.
- No classifier or email drafter on the Q&A path.

## 10. Non-goals (this slice)

- Token streaming.
- Server-side conversation store / thread IDs.
- Refactoring triage email QA to call the new console agent.
- FastAPI BFF beyond the minimal `/qa` surface needed.
- Access-control policy expansion beyond existing auth patterns (UC-053 follow-ups later).
