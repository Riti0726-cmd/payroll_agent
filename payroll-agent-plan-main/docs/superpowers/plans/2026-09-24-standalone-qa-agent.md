# Standalone Q&A Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone MCP-backed Q&A agent on `POST /qa` and wire the web Q&A console to it (no classifier/drafter).

**Architecture:** Same process as ResponsesHostServer; mount `POST /qa` via `server.app.add_route`. Q&A agent = `langchain.agents.create_agent` + Cortex MCP tools + structured `{answer, sources}`. UI uses `VITE_QA_INVOKE_URL` (Vite proxies `/api/qa` → `http://127.0.0.1:8088/qa`).

**Tech Stack:** LangGraph/LangChain `create_agent`, Starlette request/response on ResponsesAgentServerHost, React/Vite, pytest + vitest.

**Spec:** `docs/superpowers/specs/2026-09-24-standalone-qa-agent-design.md`

## Global Constraints

- Triage / Foundry `/responses` path must remain unchanged.
- Q&A must not invent payroll numbers; honest failure when MCP unavailable.
- UI must not fall back to Foundry triage invoke for Q&A.
- Do not commit unless the user asks.

## File map

| File | Responsibility |
|---|---|
| `src/payroll_specialist/models.py` | `QaSource`, chat request/response models |
| `src/payroll_specialist/qa_agent.py` | Build + run standalone Q&A agent |
| `src/payroll_specialist/qa_http.py` | `POST /qa` Starlette handler |
| `src/payroll_specialist/main.py` | Mount `/qa` on Responses host |
| `src/payroll_specialist/prompts.py` | Console Q&A system prompt (if separated) |
| `web/src/api/qa.ts` | `invokeQaChat` client |
| `web/src/pages/QaPage.tsx` | Use QA client + sources |
| `web/vite.config.ts` | Proxy `/api/qa` → `:8088/qa` |
| `web/.env.example`, `web/.env`, READMEs | `VITE_QA_INVOKE_URL` |
| `tests/test_qa_agent.py`, `tests/test_qa_http.py` | Backend tests |
| `web/src/api/qa.test.ts` | Frontend client tests |

---

### Task 1: Backend models + Q&A agent

**Files:**
- Modify: `src/payroll_specialist/models.py`
- Create: `src/payroll_specialist/qa_agent.py`
- Modify: `src/payroll_specialist/prompts.py` (add `QA_CHAT_INSTRUCTIONS`)
- Test: `tests/test_qa_agent.py`

- [ ] Add pydantic models `QaSource`, `QaChatResponse`; validate request messages in agent/http layer
- [ ] Implement `create_qa_agent(model, tools)` and `async run_qa_chat(messages, *, agent=None, tools=None) -> QaChatResponse`
- [ ] Tests with fake model/tools: empty messages rejected; MCP-unavailable stub yields honest answer + empty/error sources; happy path returns answer+sources

### Task 2: HTTP route + main mount

**Files:**
- Create: `src/payroll_specialist/qa_http.py`
- Modify: `src/payroll_specialist/main.py`
- Test: `tests/test_qa_http.py`

- [ ] `make_qa_route(runner)` → Starlette handler: parse JSON, 400 on bad body, 200 JSON `{answer,sources}`, 502 on hard failure
- [ ] In `main()`, after `ResponsesHostServer(graph)`, `server.app.add_route("/qa", handler, methods=["POST"])`
- [ ] CORS: allow browser if needed (proxy preferred for local)

### Task 3: Web client + QaPage + proxy/env/docs

**Files:**
- Create: `web/src/api/qa.ts`, `web/src/api/qa.test.ts`
- Modify: `web/src/pages/QaPage.tsx`, `web/vite.config.ts`, `web/.env.example`, `web/.env`, `web/README.md`, root `README.md` as needed
- Optionally extend `ChatMessage.sources` to richer type or map `label` strings for existing UI

- [ ] `invokeQaChat(messages, token?)` posts to `VITE_QA_INVOKE_URL`
- [ ] QaPage sends full history; renders answer; maps sources into panel
- [ ] Proxy `/api/qa` → `http://127.0.0.1:8088/qa`; default env `/api/qa`
- [ ] Vitest for client body shape + error handling

### Task 4: Verify

- [ ] `pytest tests/test_qa_agent.py tests/test_qa_http.py -v`
- [ ] `cd web && npm test -- --run src/api/qa.test.ts`
- [ ] Confirm existing triage tests still pass
