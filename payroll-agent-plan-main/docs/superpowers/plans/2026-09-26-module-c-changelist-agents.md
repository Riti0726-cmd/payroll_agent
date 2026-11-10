# Module C Changelist Agents (Full B) Implementation Plan

> **For agentic workers:** Use TDD. Steps use checkbox syntax.

**Goal:** Validation + changelist agent + due/priority + HITL line edit per `docs/superpowers/specs/2026-09-26-module-c-changelist-agents-design.md`

**Architecture:** Extend email subgraph: classifier → validation → (clarify | qa | changelist→due_priority | todo) → draft/route; persist rich Neon payload; PATCH lines.

**Tech Stack:** LangGraph, Pydantic, Starlette, React/Vitest, pytest

## Global Constraints

- Never invent payroll figures or IDs
- No PRISM/iSolved write-back
- `PAYROLL_MCP_OFFLINE=1` for CI stubs
- Keep empty-shell merge guard for existing rich `changes`

---

### Task 1: Models + due/priority helpers + classifier fields
### Task 2: Validation + changelist nodes + graph wiring
### Task 3: Orchestrator persist rich payload + priority + hitl
### Task 4: Mapping + PATCH lines API
### Task 5: Web types + edit UI + client
### Task 6: Update prompts/drafter; fix graph tests
