# Change-list lines Implementation Plan

> **For agentic workers:** TDD. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Map Neon `changes` → UI lines; never overwrite rich changelist payloads with empty shells.

**Architecture:** Read fix in `changelists_mapping.py`; write fix in triage persist + optional `get_changelist_response` on repo.

**Tech Stack:** Python, pytest, existing Neon repository / TriageOrchestrator.

**Spec:** `docs/superpowers/specs/2026-09-25-changelist-lines-design.md`

---

### Task 1: Mapper — `changes` → lines

**Files:**
- Modify: `tests/test_changelists_mapping.py`
- Modify: `src/payroll_specialist/changelists_mapping.py`

- [x] Add failing tests: changes-only, lines-wins-over-changes, parameters.client_id
- [x] Run tests → RED
- [x] Implement mapping + stringify helpers
- [x] Run tests → GREEN

### Task 2: Triage — merge on persist

**Files:**
- Modify: `src/payroll_specialist/db/repository.py` (add `get_changelist_response`)
- Modify: `src/payroll_specialist/triage/orchestrator.py`
- Modify: `tests/test_triage_workbench_persist.py`

- [x] Add failing test: existing rich `changes` preserved on re-persist
- [x] Run → RED
- [x] Implement get + merge in `_persist_workbench_payloads`
- [x] Run → GREEN
- [x] Mark spec Status approved/implemented

### Task 3: Verify

- [x] `pytest tests/test_changelists_mapping.py tests/test_triage_workbench_persist.py -q`
