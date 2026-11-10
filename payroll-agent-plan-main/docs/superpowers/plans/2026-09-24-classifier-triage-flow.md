# Classifier, Extract & Full Triage Flow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When `TRIAGE_RUN` starts, skip already-processed emails, load thread context, and run the full LangGraph (classify → qa | draft | route) per remaining email with Core R1 extraction fields.

**Architecture:** Extend `ClassificationResult` + classifier prompts. Enrich Graph `MailMessage` with `conversation_id` and body. Add thread assembly + processed-ID checks (Neon `EmailRepository`, with local-store fallback). Change `TriageOrchestrator` to drive a per-email subgraph (no intake `TRIAGE_RUN` short-circuit). Keep `POST /qa` unchanged.

**Tech Stack:** Python 3.11+, LangGraph, LangChain structured output, Pydantic, pytest, Microsoft Graph, Neon/SQLAlchemy (existing), local/blob triage store.

**Spec:** `docs/superpowers/specs/2026-09-24-classifier-triage-flow-design.md`

## Global Constraints

- Engine categories remain `qa | changelist | todo | out_of_scope` (+ `oos_destination`); do not adopt sheet enum at runtime.
- Never invent `client_id`, `employee_id`, `employee_name`, or `effective_date` — missing → `null`.
- Dedupe key = Outlook Message ID; new Message ID in an old conversation is still processed.
- Mark processed only after successful per-email graph completion.
- `POST /qa` / `qa_agent.py` behavior must not change in this plan.
- Heuristic keyword classify = fallback only (no API key / offline tests).
- Thread load cap = **10** prior messages (excluding current) unless tests override.
- Commits: only when the user explicitly asks; skip “Commit” steps during execution unless requested.
- Prefer absolute imports as used today under `src/payroll_specialist` (tests add that path via `conftest`).

---

## File structure

| File | Responsibility |
|---|---|
| `src/payroll_specialist/models.py` | Extend `ClassificationResult` + `TriageMessage` with Core R1 fields |
| `src/payroll_specialist/prompts.py` | Update `CLASSIFIER_INSTRUCTIONS` for Core R1 + sheet→engine mapping hints |
| `src/payroll_specialist/triage/mailbox.py` | `MailMessage.conversation_id`, `body`; Graph `$select` |
| `src/payroll_specialist/triage/thread.py` | **Create** — assemble current-request text from thread |
| `src/payroll_specialist/triage/processed.py` | **Create** — `ProcessedMailPort` (Neon + local fallback) |
| `src/payroll_specialist/triage/orchestrator.py` | Dedupe → thread → `process_email_fn` → mark processed |
| `src/payroll_specialist/triage/email_graph.py` | **Create** — compile START→classifier→… subgraph (no intake) |
| `src/payroll_specialist/graph.py` | Build email subgraph; inject `process_email_fn` into orchestrator |
| `src/payroll_specialist/nodes/classifier.py` | Persist new fields in fallbacks; do not skip when `mode=="email"` |
| `src/payroll_specialist/db/repository.py` | Add `is_processed(message_id) -> bool` |
| `src/payroll_specialist/db/categories.py` | Allow `out_of_scope` in serialize/parse when saving |
| `docs/taxonomy-mapping.md` | **Create** — sheet label → engine category |
| `tests/test_models.py` | Core R1 field tests |
| `tests/test_thread_assemble.py` | **Create** |
| `tests/test_processed_mail.py` | **Create** |
| `tests/test_mailbox_fields.py` | **Create** |
| `tests/test_triage_full_flow.py` | **Create** — integration: skip + process + second run |

---

### Task 1: Core R1 classification schema + prompts

**Files:**
- Modify: `src/payroll_specialist/models.py`
- Modify: `src/payroll_specialist/prompts.py`
- Modify: `tests/test_models.py`
- Modify: `src/payroll_specialist/nodes/classifier.py` (fallback dicts include new keys as `None`)
- Modify: `src/payroll_specialist/triage/orchestrator.py` (heuristic `_classify_email_text` return dict includes new keys as `None`)

**Interfaces:**
- Produces: `ClassificationResult` with optional `client_id`, `employee_name`, `effective_date: str | None`
- Produces: updated `CLASSIFIER_INSTRUCTIONS` text

- [ ] **Step 1: Write failing tests for new fields**

Add to `tests/test_models.py`:

```python
def test_classification_core_r1_fields():
    model = ClassificationResult(
        category="changelist",
        intent="Update hourly rate",
        client_id="CLI-9",
        employee_name="Ada Lovelace",
        effective_date="2026-10-01",
        employee_id="EMP-1042",
        pay_period="2026-09",
    )
    assert model.client_id == "CLI-9"
    assert model.employee_name == "Ada Lovelace"
    assert model.effective_date == "2026-10-01"


def test_classification_core_r1_defaults_null():
    model = ClassificationResult(category="qa", intent="Pay variance")
    assert model.client_id is None
    assert model.employee_name is None
    assert model.effective_date is None
```

- [ ] **Step 2: Run tests — expect fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_models.py::test_classification_core_r1_fields tests/test_models.py::test_classification_core_r1_defaults_null -v`  
Expected: FAIL (fields missing on model)

- [ ] **Step 3: Extend models**

In `ClassificationResult` and `TriageMessage`, add:

```python
client_id: str | None = Field(default=None, description="Client ID only when explicitly present. Never invent.")
employee_name: str | None = Field(default=None, description="Employee name only when explicitly present. Never invent.")
effective_date: str | None = Field(
    default=None,
    description="Effective or due date as stated (ISO YYYY-MM-DD when possible). Never invent.",
)
```

(`TriageMessage` uses plain optional attributes, not Field.)

- [ ] **Step 4: Update `CLASSIFIER_INSTRUCTIONS`**

Append extraction rules: extract `client_id`, `employee_name`, `effective_date` only when stated; never invent. Keep four categories + `oos_destination`. Add one line mapping hints: pay-change/bank/W-4 → `changelist`; timesheet/off-cycle/approval → `todo`; paycheck questions → `qa`; benefits/tax/WC → `out_of_scope`.

- [ ] **Step 5: Update heuristic/fallback dicts**

In `classifier.py` fallbacks and `orchestrator._classify_email_text`, include `"client_id": None, "employee_name": None, "effective_date": None`.

- [ ] **Step 6: Run tests — expect pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_models.py -v`  
Expected: PASS

---

### Task 2: Mailbox conversation_id + body

**Files:**
- Modify: `src/payroll_specialist/triage/mailbox.py`
- Create: `tests/test_mailbox_fields.py`

**Interfaces:**
- Produces: `MailMessage(..., body: str = "", conversation_id: str = "")`
- Consumes: Graph `$select` including `conversationId,body`

- [ ] **Step 1: Write failing test**

```python
from triage.mailbox import MailMessage, MockGraphMailbox

def test_mock_mailbox_preserves_conversation_and_body():
    mb = MockGraphMailbox(
        [
            MailMessage(
                id="m1",
                received_at="2026-09-01T10:00:00Z",
                subject="Pay",
                body_preview="preview",
                body="full body EMP-1",
                conversation_id="conv-1",
            )
        ]
    )
    mb.bind_specialist("s1", "box1")
    msgs = mb.list_messages(
        "box1",
        window_start="2026-09-01T00:00:00Z",
        window_end="2026-09-02T00:00:00Z",
    )
    assert msgs[0].conversation_id == "conv-1"
    assert msgs[0].body == "full body EMP-1"
```

- [ ] **Step 2: Run test — expect fail** (missing fields)

- [ ] **Step 3: Extend `MailMessage`**

```python
@dataclass
class MailMessage:
    id: str
    received_at: str
    from_address: str = ""
    subject: str = ""
    body_preview: str = ""
    body: str = ""
    conversation_id: str = ""
    is_read: bool = False
    web_link: str = ""
```

- [ ] **Step 4: Update `RealGraphMailbox.list_messages`**

Change `$select` to:  
`id,receivedDateTime,from,subject,bodyPreview,body,conversationId,isRead,webLink`

When building `MailMessage`, set:

```python
body=(item.get("body") or {}).get("content") or item.get("bodyPreview") or "",
conversation_id=item.get("conversationId") or "",
```

- [ ] **Step 5: Run mailbox tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_mailbox_fields.py tests/test_store_mailbox.py -v`  
Expected: PASS

---

### Task 3: Thread current-request assembly

**Files:**
- Create: `src/payroll_specialist/triage/thread.py`
- Create: `tests/test_thread_assemble.py`

**Interfaces:**
- Produces: `assemble_current_request(*, subject: str, current_body: str, prior_bodies: list[str], max_prior: int = 10) -> str`
- Consumes: `prior_bodies` ordered oldest→newest; uses last `max_prior` entries

- [ ] **Step 1: Write failing tests**

```python
from triage.thread import assemble_current_request

def test_assemble_includes_subject_and_current():
    text = assemble_current_request(
        subject="Rate change",
        current_body="Please update EMP-9 to $50 effective 2026-10-01",
        prior_bodies=["Old question about August pay"],
    )
    assert "Rate change" in text
    assert "EMP-9" in text
    assert "Old question" in text


def test_assemble_caps_prior():
    priors = [f"msg-{i}" for i in range(20)]
    text = assemble_current_request(
        subject="S",
        current_body="latest",
        prior_bodies=priors,
        max_prior=3,
    )
    assert "msg-17" in text
    assert "msg-0" not in text
```

- [ ] **Step 2: Run — expect fail**

- [ ] **Step 3: Implement `triage/thread.py`**

```python
def assemble_current_request(
    *,
    subject: str,
    current_body: str,
    prior_bodies: list[str],
    max_prior: int = 10,
) -> str:
    prior = prior_bodies[-max_prior:] if max_prior > 0 else []
    parts = [f"Subject: {subject.strip()}"]
    if prior:
        parts.append("Prior thread (oldest to newest):")
        for i, body in enumerate(prior, 1):
            parts.append(f"[{i}] {(body or '').strip()[:2000]}")
    parts.append("Current message:")
    parts.append((current_body or "").strip())
    return "\n".join(parts).strip()
```

- [ ] **Step 4: Run — expect pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_thread_assemble.py -v`

---

### Task 4: Processed-mail port (dedupe)

**Files:**
- Modify: `src/payroll_specialist/db/repository.py` — add `is_processed`
- Modify: `src/payroll_specialist/db/categories.py` — allow `out_of_scope`
- Create: `src/payroll_specialist/triage/processed.py`
- Create: `tests/test_processed_mail.py`

**Interfaces:**
- Produces: `EmailRepository.is_processed(message_id: str) -> bool`
- Produces: `LocalProcessedMailStore` with `is_processed(id) -> bool`, `mark_processed(id) -> None`
- Local path: JSON set under `root / "processed" / f"{specialist_id}.json"`

- [ ] **Step 1: Write failing tests for local fallback**

```python
from pathlib import Path
from triage.processed import LocalProcessedMailStore

def test_local_processed_roundtrip(tmp_path: Path):
    store = LocalProcessedMailStore(tmp_path, specialist_id="demo")
    assert store.is_processed("m1") is False
    store.mark_processed("m1")
    assert store.is_processed("m1") is True
```

- [ ] **Step 2: Run — expect fail**

- [ ] **Step 3: Implement `LocalProcessedMailStore` in `triage/processed.py`**

Persist a JSON list/set of message IDs per specialist under `root / "processed" / f"{specialist_id}.json"`.

- [ ] **Step 4: Add `EmailRepository.is_processed`**

```python
def is_processed(self, message_id: str) -> bool:
    with self._session_factory() as session:
        row = session.execute(
            select(EmailProcessing).where(EmailProcessing.message_id == str(message_id))
        ).scalar_one_or_none()
        return bool(row and row.is_processed)
```

- [ ] **Step 5: Add `get_processed_mail_port()`** in `triage/processed.py` that prefers Neon when DB env is configured, else `LocalProcessedMailStore`.

- [ ] **Step 6: Allow `out_of_scope` in `db/categories.py` `ALLOWED_CATEGORIES`**

- [ ] **Step 7: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_processed_mail.py -v`  
Expected: PASS

---

### Task 5: Per-email LangGraph subgraph (no intake)

**Files:**
- Create: `src/payroll_specialist/triage/email_graph.py`
- Modify: `src/payroll_specialist/graph.py`
- Modify: `src/payroll_specialist/nodes/classifier.py` — `mode == "email"` always classifies
- Modify: `tests/test_graph_routes.py` — add email-subgraph test

**Interfaces:**
- Produces: `build_email_processing_graph(...)` → compiled graph
- Produces: `async def run_email_graph(graph, query: str) -> dict` with keys `triage`, `draft`, `qa_findings`
- Input state: `{"messages": [HumanMessage(content=query)], "query": query, "mode": "email"}`

- [ ] **Step 1: Write failing test** for `run_email_graph` with `MockChatModel` (reuse pattern from `tests/test_graph_routes.py`) asserting `triage["category"]` and a draft/routing outcome.

- [ ] **Step 2: Run — expect fail**

- [ ] **Step 3: Implement `email_graph.py`**

Compile `StateGraph(PayrollState)`:

- START → `classifier` → conditional `route_by_category` → `qa_specialist` | `drafting_specialist` | `routing_agent`
- `qa_specialist` → `drafting_specialist` → END
- `routing_agent` → END
- direct `drafting_specialist` → END

Export `run_email_graph` as above.

- [ ] **Step 4: Wire from `create_payroll_graph`**

```python
email_graph = build_email_processing_graph(...)
async def process_email_fn(query: str) -> dict:
    return await run_email_graph(email_graph, query)

orchestrator = triage_orchestrator or TriageOrchestrator(process_email_fn=process_email_fn)
```

- [ ] **Step 5: Classifier early-return**

Keep early-return only when `mode == "triage" and triage_summary`. Never early-return for `mode == "email"`.

- [ ] **Step 6: Run graph tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_graph_routes.py -v`  
Expected: PASS

---

### Task 6: Orchestrator — dedupe + thread + full graph per email

**Files:**
- Modify: `src/payroll_specialist/triage/orchestrator.py`
- Create: `tests/test_triage_full_flow.py`

**Interfaces:**
- Consumes: `process_email_fn: Callable[[str], Awaitable[dict]] | None`, `ProcessedMailPort`, `assemble_current_request`
- Produces: `email_results` with `message_id`, `conversation_id`, `category`, Core R1 fields, `skipped`, `status`, optional `draft`

- [ ] **Step 1: Write integration test** `tests/test_triage_full_flow.py`

Scenario:

1. Seed two messages same `conversation_id`; mark older Message ID processed.
2. `fake_process_email_fn` returns qa triage + draft; assert it sees thread/current text for the new mail.
3. First `orch.run` → old skipped, new succeeded + marked processed.
4. Second `orch.run` → both skipped.

Use `LocalTriageStore`, `MockGraphMailbox`, `LocalProcessedMailStore`, high `lookback_days`.

- [ ] **Step 2: Run — expect fail**

- [ ] **Step 3: Rewrite orchestrator loop**

For each message:

1. If `processed_store.is_processed(msg.id)` → append skipped result; continue.
2. `body = msg.body or msg.body_preview`
3. `conv = msg.conversation_id or msg.id`
4. Build `prior_bodies` from other messages in the fetched window with same `conversation_id` and earlier `received_at` (oldest→newest), capped at 10.
5. `query = assemble_current_request(...)`
6. Call `process_email_fn(query)` if set; else heuristic `_classify_email_text`
7. On success: append result with Core R1 fields + draft; `mark_processed(msg.id)`
8. On failure: append `status=failed`; do **not** mark processed; continue

Update `_format_summary` for skipped vs processed counts.

- [ ] **Step 4: Run integration test — expect pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_triage_full_flow.py -v`

- [ ] **Step 5: Full offline suite**

Run: `.\.venv\Scripts\python.exe -m pytest tests -v`  
Expected: PASS

---

### Task 7: Taxonomy mapping doc + README pointer

**Files:**
- Create: `docs/taxonomy-mapping.md`
- Modify: `README.md`

- [ ] **Step 1: Write `docs/taxonomy-mapping.md`** with the mapping table from the spec.

- [ ] **Step 2: README Architecture** — note triage runs full per-email graph with dedupe/thread; console Q&A is `POST /qa`; see `docs/taxonomy-mapping.md`.

---

## Spec coverage checklist

| Spec item | Task |
|---|---|
| Core R1 fields + never invent | Task 1 |
| Engine taxonomy kept | Task 1, 7 |
| Graph conversationId + body | Task 2 |
| Thread assemble / current request | Task 3 |
| Dedupe skip processed | Task 4, 6 |
| Full LangGraph per email | Task 5, 6 |
| Mark processed on success only | Task 6 |
| Chat/`POST /qa` unchanged | Global constraint |
| Heuristic fallback | Task 1, 6 |
| Telemetry step names | Task 6 |
| UC-017 rules engine deferred | Non-goal |

## Placeholder / consistency self-check

- APIs: `assemble_current_request`, `process_email_fn`, `LocalProcessedMailStore`, `run_email_graph`, `mode="email"`.
- Field names aligned across model, prompt, orchestrator results.
- Commit steps omitted unless user requests.
