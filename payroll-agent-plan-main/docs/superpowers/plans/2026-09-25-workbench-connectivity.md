# Workbench Connectivity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire Settings, Drafts, and Change lists to Starlette APIs (triage store + Neon), including Accept/Discard and Approve/Request-clarification HITL status writes — no Snowflake, no Graph Send.

**Architecture:** Mirror Queue: add `hitl_status` on `email_processing`; repository list/update helpers; pure mappers; `settings_http` / `drafts_http` / `changelists_http` on Responses host; triage persists draft + minimal changelist JSON shell when payloads exist; web clients + Vite proxies load/save each page.

**Tech Stack:** Python 3 + Starlette + SQLAlchemy (`EmailRepository`), local/blob triage store, Vite/React/TS, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-09-25-workbench-connectivity-design.md`

## Global Constraints

- No Snowflake / Cortex MCP changes.
- Draft **Send** stays toast “Not connected yet.”
- Do not invent rich changelist field/from/to extractors; empty `lines: []` is OK.
- Drafts / Change lists require Neon — missing `DATABASE_URL` → HTTP 503.
- Settings use triage store only (no Neon required).
- HITL status lives in `hitl_status` text column — do not overload `is_processed` alone for Accept vs Discard.
- Commits: only when the user asks during execution; skip plan “Commit” steps unless explicitly requested.
- No FastAPI BFF.

---

## File structure

```text
sql/
  002_add_hitl_status.sql          # NEW

src/payroll_specialist/
  db/models.py                     # hitl_status column
  db/repository.py                 # list/update drafts + changelists + set_hitl_status
  models.py                        # Settings / Draft / ChangeList response models
  drafts_mapping.py                # NEW
  changelists_mapping.py           # NEW
  settings_http.py                 # NEW — GET/PUT /settings
  drafts_http.py                   # NEW — GET /drafts, PATCH /drafts/{id}
  changelists_http.py              # NEW — GET /changelists, PATCH /changelists/{id}
  triage/orchestrator.py           # persist draft + changelist shell
  main.py                          # mount three route modules

tests/
  test_email_repository_workbench.py
  test_drafts_mapping.py
  test_changelists_mapping.py
  test_settings_http.py
  test_drafts_http.py
  test_changelists_http.py
  test_triage_workbench_persist.py

web/
  src/api/settings.ts + settings.test.ts
  src/api/drafts.ts + drafts.test.ts
  src/api/changelists.ts + changelists.test.ts
  src/pages/SettingsPage.tsx
  src/pages/DraftsPage.tsx
  src/pages/ChangeListsPage.tsx
  vite.config.ts
  .env.example
  README.md
```

---

### Task 1: `hitl_status` + repository list/update

**Files:**
- Create: `sql/002_add_hitl_status.sql`
- Modify: `src/payroll_specialist/db/models.py`
- Modify: `src/payroll_specialist/db/repository.py`
- Create: `tests/test_email_repository_workbench.py`

**Interfaces:**
- Produces:
  - Column `EmailProcessing.hitl_status: str | None`
  - `EmailRepository.set_hitl_status(message_id: str, status: str, *, draft_body: str | None = None) -> dict`
  - `EmailRepository.list_pending_drafts(specialist_mailbox: str, limit: int = 200) -> list[dict]`
  - `EmailRepository.list_pending_changelists(specialist_mailbox: str, limit: int = 200) -> list[dict]`
  - Dict keys for drafts: `message_id`, `subject`, `sender_email`, `draft_content`, `hitl_status`, `sub_content`
  - Dict keys for changelists: `message_id`, `subject`, `category`, `sub_content`, `changelist_response`, `hitl_status`, `email_received_dttm`

- [ ] **Step 1: Write failing repository tests**

Create `tests/test_email_repository_workbench.py` (mock session pattern from `tests/test_email_repository_queue.py`):

```python
from unittest.mock import MagicMock

from db.repository import EmailNotFoundError, EmailRepository


def test_set_hitl_status_updates_and_optional_body():
    row = MagicMock()
    row.message_id = "m1"
    row.draft_content = "old"
    row.hitl_status = "pending"
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.execute.return_value.scalar_one_or_none.return_value = row
    factory = MagicMock(return_value=session)
    repo = EmailRepository(factory)

    out = repo.set_hitl_status("m1", "accepted", draft_body="new body")
    assert row.hitl_status == "accepted"
    assert row.draft_content == "new body"
    session.commit.assert_called()
    assert out["message_id"] == "m1"


def test_set_hitl_status_missing_raises():
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.execute.return_value.scalar_one_or_none.return_value = None
    repo = EmailRepository(MagicMock(return_value=session))
    try:
        repo.set_hitl_status("missing", "discarded")
        assert False, "expected EmailNotFoundError"
    except EmailNotFoundError:
        pass


def test_list_pending_drafts_empty_mailbox():
    repo = EmailRepository(MagicMock())
    assert repo.list_pending_drafts(specialist_mailbox="  ") == []


def test_list_pending_changelists_empty_mailbox():
    repo = EmailRepository(MagicMock())
    assert repo.list_pending_changelists(specialist_mailbox="") == []
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd "c:\Users\Harshdeep\Downloads\Payroll - Agent - Plan"
.\.venv\Scripts\python.exe -m pytest tests/test_email_repository_workbench.py -v
```

Expected: FAIL (methods missing)

- [ ] **Step 3: Add SQL + ORM + repository methods**

`sql/002_add_hitl_status.sql`:

```sql
ALTER TABLE email_processing
    ADD COLUMN IF NOT EXISTS hitl_status TEXT NULL;
```

In `db/models.py`, add after `changelist_response`:

```python
hitl_status: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Implement on `EmailRepository`:

- `set_hitl_status`: load by `message_id`; set `hitl_status`; if `draft_body is not None`, set `draft_content`; commit; return a dict suitable for mapping (include fields needed by drafts/changelists mappers).
- `list_pending_drafts`: `is_drafted IS TRUE`, `draft_content IS NOT NULL`, `(hitl_status IS NULL OR hitl_status = 'pending')`, mailbox `like` (same as `list_open_queue`), order `mail_draft_time.desc().nullslast()` then `email_received_dttm.desc()`.
- `list_pending_changelists`: category matches changelist via `parse_categories` filter in Python **or** SQL `category.ilike('%changelist%')` plus post-filter with `parse_categories`; `(hitl_status IS NULL OR hitl_status = 'pending')`; same mailbox scope; order `email_received_dttm.desc()`.

Also extend `save_draft` to set `hitl_status = "pending"` when saving a new draft.

- [ ] **Step 4: Run — expect PASS**

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_email_repository_workbench.py -v
```

- [ ] **Step 5: Commit** (skip unless user asked)

---

### Task 2: Draft + changelist mapping (TDD)

**Files:**
- Create: `src/payroll_specialist/drafts_mapping.py`
- Create: `src/payroll_specialist/changelists_mapping.py`
- Modify: `src/payroll_specialist/models.py`
- Create: `tests/test_drafts_mapping.py`
- Create: `tests/test_changelists_mapping.py`

**Interfaces:**
- Produces:
  - `row_to_draft_item(row: Mapping[str, Any]) -> dict`
  - `row_to_changelist_item(row: Mapping[str, Any]) -> dict`
  - Pydantic: `DraftItemResponse`, `DraftListResponse`, `ChangeListLineResponse`, `ChangeListItemResponse`, `ChangeListListResponse`, `SettingsRunResponse`, `SettingsResponse`, `SettingsUpdateRequest`

- [ ] **Step 1: Write failing mapping tests**

`tests/test_drafts_mapping.py`:

```python
from drafts_mapping import row_to_draft_item


def test_row_to_draft_item_happy():
    item = row_to_draft_item(
        {
            "message_id": "m1",
            "subject": "Pay question",
            "sender_email": "e@x.com",
            "draft_content": "Hello",
            "hitl_status": "pending",
        }
    )
    assert item == {
        "id": "m1",
        "subject": "Pay question",
        "to": "e@x.com",
        "body": "Hello",
        "status": "pending",
        "relatedQueueId": "m1",
    }


def test_row_to_draft_item_fallbacks():
    item = row_to_draft_item(
        {
            "message_id": "m2",
            "subject": None,
            "sender_email": None,
            "draft_content": "",
            "hitl_status": None,
        }
    )
    assert item["subject"] == "(no subject)"
    assert item["to"] == ""
    assert item["status"] == "pending"
```

`tests/test_changelists_mapping.py`:

```python
from changelists_mapping import row_to_changelist_item


def test_row_to_changelist_empty_lines():
    item = row_to_changelist_item(
        {
            "message_id": "c1",
            "subject": "DD change",
            "sub_content": '{"client_id":"C9"}',
            "changelist_response": None,
            "hitl_status": "pending",
        }
    )
    assert item["id"] == "c1"
    assert item["clientId"] == "C9"
    assert item["title"] == "DD change"
    assert item["lines"] == []


def test_row_to_changelist_parses_lines():
    import json

    payload = {
        "lines": [
            {"id": "l1", "field": "bank", "from": "1", "to": "2", "reviewed": False}
        ]
    }
    item = row_to_changelist_item(
        {
            "message_id": "c2",
            "subject": None,
            "sub_content": None,
            "changelist_response": json.dumps(payload),
            "hitl_status": None,
        }
    )
    assert item["clientId"] == "unknown"
    assert item["title"] == "(no subject)"
    assert item["lines"][0]["field"] == "bank"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_drafts_mapping.py tests/test_changelists_mapping.py -v
```

- [ ] **Step 3: Implement mappers + models**

Add to `models.py`:

```python
class DraftItemResponse(BaseModel):
    id: str
    subject: str
    to: str
    body: str
    status: Literal["pending", "accepted", "discarded", "sent"]
    relatedQueueId: str | None = None


class DraftListResponse(BaseModel):
    items: list[DraftItemResponse] = Field(default_factory=list)


class ChangeListLineResponse(BaseModel):
    id: str
    field: str
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None
    reviewed: bool = False

    model_config = {"populate_by_name": True}


class ChangeListItemResponse(BaseModel):
    id: str
    clientId: str
    title: str
    lines: list[ChangeListLineResponse] = Field(default_factory=list)


class ChangeListListResponse(BaseModel):
    items: list[ChangeListItemResponse] = Field(default_factory=list)


class SettingsRunResponse(BaseModel):
    runId: str
    startedAt: str
    status: str
    result: str = ""


class SettingsResponse(BaseModel):
    lookbackDays: int
    mode: Literal["manual", "recurring"]
    intervalHours: Literal[2, 4, 24]
    runs: list[SettingsRunResponse] = Field(default_factory=list)


class SettingsUpdateRequest(BaseModel):
    lookbackDays: int = Field(ge=1)
    mode: Literal["manual", "recurring"]
    intervalHours: Literal[2, 4, 24]
```

**Note on `from`:** JSON key must be `"from"` for the web type. Prefer building line dicts in the mapper with key `"from"` and using `model_dump(by_alias=True)` on responses, **or** keep lines as plain dicts in HTTP without Pydantic nested alias pain. Simplest path that matches web `ChangeListItem`: mapper returns camelCase dicts; HTTP validates with a loose model or `ChangeListItemResponse` using `Field(validation_alias="from")`. Implementer: ensure wire JSON uses `"from"` not `"from_"`.

Reuse `parse_extracts` from `queue_mapping.py` inside changelist mapper for `client_id`.

- [ ] **Step 4: Run — expect PASS**

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_drafts_mapping.py tests/test_changelists_mapping.py -v
```

- [ ] **Step 5: Commit** (skip unless user asked)

---

### Task 3: Settings HTTP (TDD)

**Files:**
- Create: `src/payroll_specialist/settings_http.py`
- Create: `tests/test_settings_http.py`
- Modify: `src/payroll_specialist/main.py`

**Interfaces:**
- Consumes: `get_triage_store()`, `SettingsResponse`, `SettingsUpdateRequest`
- Produces: `make_settings_get_route`, `make_settings_put_route`, `mount_settings_routes(app)`

- [ ] **Step 1: Write failing handler tests**

```python
import json
import pytest
from starlette.requests import Request
from settings_http import make_settings_get_route, make_settings_put_route


def _request(method: str, query: str = b"specialist_id=default", body: bytes = b""):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": "/settings",
        "raw_path": b"/settings",
        "query_string": query,
        "headers": [(b"content-type", b"application/json")] if body else [],
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 8088),
    }

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


@pytest.mark.asyncio
async def test_settings_get_400():
    route = make_settings_get_route(
        get_fn=lambda _sid: {"lookbackDays": 7, "mode": "manual", "intervalHours": 2, "runs": []}
    )
    resp = await route(_request("GET", b""))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_settings_get_200():
    route = make_settings_get_route(
        get_fn=lambda sid: {
            "lookbackDays": 7,
            "mode": "manual",
            "intervalHours": 2,
            "runs": [
                {
                    "runId": "r1",
                    "startedAt": "2026-09-25T10:00:00+00:00",
                    "status": "succeeded",
                    "result": "ok",
                }
            ],
        }
    )
    resp = await route(_request("GET"))
    assert resp.status_code == 200
    data = json.loads(resp.body)
    assert data["lookbackDays"] == 7
    assert data["runs"][0]["runId"] == "r1"


@pytest.mark.asyncio
async def test_settings_put_400_bad_interval():
    route = make_settings_put_route(put_fn=lambda sid, payload: payload)
    body = json.dumps({"lookbackDays": 7, "mode": "manual", "intervalHours": 3}).encode()
    resp = await route(_request("PUT", body=body))
    assert resp.status_code == 400
```

- [ ] **Step 2: Run — expect FAIL**

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_settings_http.py -v
```

- [ ] **Step 3: Implement `settings_http.py` and mount**

Default GET:
1. `config = store.get_specialist_config(specialist_id)`
2. `runs = store.list_runs(specialist_id, limit=20)`
3. Map to camelCase: `lookbackDays=int(config["lookback_days"])`, `mode`, `intervalHours`, runs from `run_id`/`created_at`/`status`/`summary` (string truncate 200).

Default PUT:
1. Validate with `SettingsUpdateRequest`
2. `save_specialist_config` merging existing mailbox fields
3. Return GET-shaped payload (include refreshed runs)

In `main.py` (both hosting branches), after queue mount:

```python
from settings_http import mount_settings_routes
mount_settings_routes(server.app)
logger.info("Mounted settings API at GET/PUT /settings")
```

`mount_settings_routes` registers GET and PUT on `/settings`.

- [ ] **Step 4: Run — expect PASS**

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_settings_http.py -v
```

- [ ] **Step 5: Commit** (skip unless user asked)

---

### Task 4: Drafts HTTP (TDD)

**Files:**
- Create: `src/payroll_specialist/drafts_http.py`
- Create: `tests/test_drafts_http.py`
- Modify: `src/payroll_specialist/main.py`

**Interfaces:**
- Consumes: `row_to_draft_item`, `EmailRepository.list_pending_drafts`, `set_hitl_status`, `EmailNotFoundError`
- Produces: `make_drafts_list_route`, `make_draft_patch_route`, `mount_drafts_routes(app)`

- [ ] **Step 1: Write failing handler tests**

```python
import json
import pytest
from starlette.requests import Request
from drafts_http import make_drafts_list_route, make_draft_patch_route


def _list_request(query: bytes = b"specialist_id=default"):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/drafts",
        "raw_path": b"/drafts",
        "query_string": query,
        "headers": [],
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 8088),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


def _patch_request(message_id: str, body: dict, query: bytes = b"specialist_id=default"):
    raw = json.dumps(body).encode()
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "PATCH",
        "scheme": "http",
        "path": f"/drafts/{message_id}",
        "raw_path": f"/drafts/{message_id}".encode(),
        "query_string": query,
        "headers": [(b"content-type", b"application/json")],
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 8088),
        "path_params": {"message_id": message_id},
    }

    async def receive():
        return {"type": "http.request", "body": raw, "more_body": False}

    return Request(scope, receive)


@pytest.mark.asyncio
async def test_drafts_list_200():
    def list_fn(sid: str):
        return [
            {
                "message_id": "m1",
                "subject": "Hi",
                "sender_email": "a@b.com",
                "draft_content": "Body",
                "hitl_status": "pending",
            }
        ]

    route = make_drafts_list_route(list_fn=list_fn)
    resp = await route(_list_request())
    assert resp.status_code == 200
    assert json.loads(resp.body)["items"][0]["id"] == "m1"


@pytest.mark.asyncio
async def test_drafts_list_503():
    def boom(_sid: str):
        raise RuntimeError("DATABASE_URL is not set")

    route = make_drafts_list_route(list_fn=boom)
    resp = await route(_list_request())
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_draft_patch_accepted():
    def patch_fn(sid: str, message_id: str, status: str, body: str | None):
        assert sid == "default"
        assert message_id == "m1"
        assert status == "accepted"
        return {
            "message_id": "m1",
            "subject": "Hi",
            "sender_email": "a@b.com",
            "draft_content": body or "Body",
            "hitl_status": status,
        }

    route = make_draft_patch_route(patch_fn=patch_fn)
    resp = await route(_patch_request("m1", {"status": "accepted", "body": "Edited"}))
    assert resp.status_code == 200
    assert json.loads(resp.body)["status"] == "accepted"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_drafts_http.py -v
```

- [ ] **Step 3: Implement + mount**

Default list_fn: resolve mailbox from triage config (copy `default_list_queue` pattern), call `list_pending_drafts`.

Default patch_fn: validate status ∈ `{accepted, discarded}`; `set_hitl_status`; map with `row_to_draft_item`. Map `EmailNotFoundError` → 404; other DB errors → 503; bad status → 400.

```python
app.add_route("/drafts", make_drafts_list_route(...), methods=["GET"])
app.add_route("/drafts/{message_id}", make_draft_patch_route(...), methods=["PATCH"])
```

- [ ] **Step 4: Run — expect PASS**

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_drafts_http.py tests/test_drafts_mapping.py -v
```

- [ ] **Step 5: Commit** (skip unless user asked)

---

### Task 5: Changelists HTTP (TDD)

**Files:**
- Create: `src/payroll_specialist/changelists_http.py`
- Create: `tests/test_changelists_http.py`
- Modify: `src/payroll_specialist/main.py`

**Interfaces:**
- Same pattern as drafts; status ∈ `{approved, needs_clarification}`
- Produces: `mount_changelists_routes(app)`

- [ ] **Step 1: Write failing handler tests**

Create `tests/test_changelists_http.py`:

```python
import json
import pytest
from starlette.requests import Request
from changelists_http import make_changelists_list_route, make_changelist_patch_route


def _list_request(query: bytes = b"specialist_id=default"):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/changelists",
        "raw_path": b"/changelists",
        "query_string": query,
        "headers": [],
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 8088),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


def _patch_request(message_id: str, body: dict, query: bytes = b"specialist_id=default"):
    raw = json.dumps(body).encode()
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "PATCH",
        "scheme": "http",
        "path": f"/changelists/{message_id}",
        "raw_path": f"/changelists/{message_id}".encode(),
        "query_string": query,
        "headers": [(b"content-type", b"application/json")],
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 8088),
        "path_params": {"message_id": message_id},
    }

    async def receive():
        return {"type": "http.request", "body": raw, "more_body": False}

    return Request(scope, receive)


@pytest.mark.asyncio
async def test_changelists_list_200():
    def list_fn(sid: str):
        return [
            {
                "message_id": "c1",
                "subject": "DD",
                "category": "changelist",
                "sub_content": '{"client_id":"C1"}',
                "changelist_response": None,
                "hitl_status": "pending",
                "email_received_dttm": "2026-09-20T10:00:00+00:00",
            }
        ]

    route = make_changelists_list_route(list_fn=list_fn)
    resp = await route(_list_request())
    assert resp.status_code == 200
    item = json.loads(resp.body)["items"][0]
    assert item["id"] == "c1"
    assert item["clientId"] == "C1"
    assert item["lines"] == []


@pytest.mark.asyncio
async def test_changelists_list_503():
    def boom(_sid: str):
        raise RuntimeError("DATABASE_URL is not set")

    route = make_changelists_list_route(list_fn=boom)
    resp = await route(_list_request())
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_changelist_patch_approved():
    def patch_fn(sid: str, message_id: str, status: str):
        assert status == "approved"
        return {
            "message_id": message_id,
            "subject": "DD",
            "category": "changelist",
            "sub_content": None,
            "changelist_response": None,
            "hitl_status": status,
            "email_received_dttm": None,
        }

    route = make_changelist_patch_route(patch_fn=patch_fn)
    resp = await route(_patch_request("c1", {"status": "approved"}))
    assert resp.status_code == 200
    assert json.loads(resp.body)["id"] == "c1"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_changelists_http.py -v
```

- [ ] **Step 3: Implement + mount**

```python
# changelists_http.py — same structure as drafts_http.py
# GET /changelists → list_fn → row_to_changelist_item
# PATCH /changelists/{message_id} → status in {approved, needs_clarification}
# EmailNotFoundError → 404; DB errors → 503; bad status → 400
# set_hitl_status return dict MUST include changelist_response + sub_content for remapping
```

In `main.py`:

```python
from changelists_http import mount_changelists_routes
mount_changelists_routes(server.app)
```

- [ ] **Step 4: Run — expect PASS**

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_changelists_http.py tests/test_changelists_mapping.py -v
```

- [ ] **Step 5: Commit** (skip unless user asked)

---

### Task 6: Triage persist draft + changelist shell

**Files:**
- Modify: `src/payroll_specialist/triage/orchestrator.py`
- Create: `tests/test_triage_workbench_persist.py`

**Interfaces:**
- Extends `_persist_queue_row` or post-persist hook to also call `save_draft` / `save_changelist_response` when applicable
- Consumes: `payload["draft"]`, `triage["category"]`, extracts already saved

- [ ] **Step 1: Write failing test with FakeEmailRepo**

Create `tests/test_triage_workbench_persist.py`:

```python
from __future__ import annotations

import pytest

from db.repository import UpsertResult
from store.local_store import LocalTriageStore
from triage.mailbox import MailMessage, MockGraphMailbox
from triage.orchestrator import TriageOrchestrator
from triage.processed import LocalProcessedMailStore


class FakeEmailRepo:
    def __init__(self) -> None:
        self.upserts: list = []
        self.classifications: list = []
        self.extracts: list = []
        self.drafts: list = []
        self.changelists: list = []

    def upsert_ingested_email(self, *, message):
        self.upserts.append(message)
        return UpsertResult.inserted

    def save_classification(self, *, email_id, categories, priority="medium"):
        self.classifications.append((email_id, categories, priority))

    def save_extracts(self, *, message_id, extracts):
        self.extracts.append((message_id, extracts))

    def save_draft(self, *, email_id, draft_content):
        self.drafts.append((email_id, draft_content))

    def save_changelist_response(self, message_id, payload):
        self.changelists.append((message_id, payload))


@pytest.mark.asyncio
async def test_triage_persists_draft_and_changelist_shell(tmp_path):
    store = LocalTriageStore(str(tmp_path / "triage"))
    processed = LocalProcessedMailStore(tmp_path / "proc", specialist_id="demo")
    mb = MockGraphMailbox(
        [
            MailMessage(
                id="m-cl",
                received_at="2026-09-10T13:00:00Z",
                from_address="client@example.com",
                subject="Direct deposit",
                body="Please update my bank account",
                conversation_id="c1",
            ),
        ]
    )
    repo = FakeEmailRepo()

    async def fake_process(_query: str) -> dict:
        return {
            "triage": {
                "category": "changelist",
                "intent": "Update DD",
                "confidence": 0.9,
                "employee_id": None,
                "pay_period": None,
                "client_id": "C1",
                "employee_name": None,
                "effective_date": None,
                "oos_destination": None,
            },
            "draft": "Please use the portal to update direct deposit.",
            "qa_findings": None,
        }

    orch = TriageOrchestrator(
        store=store,
        mailbox=mb,
        process_email_fn=fake_process,
        processed_store=processed,
        email_repo=repo,
    )
    store.save_specialist_config(
        "demo",
        {"mailbox_id": "hrc@example.com", "lookback_days": 30, "mode": "manual"},
    )
    out = await orch.run(specialist_id="demo", mailbox_id="hrc@example.com")
    assert out["email_results"][0]["status"] == "succeeded"
    assert repo.drafts == [("m-cl", "Please use the portal to update direct deposit.")]
    assert len(repo.changelists) == 1
    assert repo.changelists[0][0] == "m-cl"
    assert repo.changelists[0][1]["lines"] == []
    assert repo.changelists[0][1]["clientId"] == "C1"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_triage_workbench_persist.py -v
```

- [ ] **Step 3: Wire orchestrator**

After successful `_persist_queue_row` in the succeeded path (where `payload` is available), call:

```python
draft = (payload.get("draft") or "").strip()
if draft:
    repo.save_draft(email_id=msg.id, draft_content=draft)

if (triage.get("category") or "") == "changelist":
    repo.save_changelist_response(
        msg.id,
        {
            "clientId": triage.get("client_id") or "unknown",
            "title": (msg.subject or "").strip() or "(no subject)",
            "lines": [],
            "status": "pending",
        },
    )
```

Keep these calls inside the same try/except as Neon persist so failures mark the email result failed.

- [ ] **Step 4: Run — expect PASS**

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_triage_workbench_persist.py tests/test_triage_neon_persist.py -v
```

- [ ] **Step 5: Commit** (skip unless user asked)

---

### Task 7: Web Settings client + page

**Files:**
- Create: `web/src/api/settings.ts`
- Create: `web/src/api/settings.test.ts`
- Modify: `web/src/pages/SettingsPage.tsx`
- Modify: `web/vite.config.ts`
- Modify: `web/.env.example`

**Interfaces:**
- `fetchSettings(specialistId, token?)`, `saveSettings(specialistId, payload, token?)`, `SettingsError`

- [ ] **Step 1: Write failing `settings.test.ts`**

```typescript
import { fetchSettings, saveSettings, SettingsError } from "./settings";

describe("settings api", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_SETTINGS_URL", "https://example.test/settings");
    vi.stubGlobal("fetch", vi.fn());
  });

  it("GETs with specialist_id", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          lookbackDays: 7,
          mode: "manual",
          intervalHours: 2,
          runs: [],
        }),
        { status: 200 },
      ),
    );
    await fetchSettings("default", "tok");
    expect(fetch).toHaveBeenCalledWith(
      "https://example.test/settings?specialist_id=default",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer tok" }),
      }),
    );
  });

  it("PUTs body", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          lookbackDays: 14,
          mode: "recurring",
          intervalHours: 4,
          runs: [],
        }),
        { status: 200 },
      ),
    );
    await saveSettings("default", {
      lookbackDays: 14,
      mode: "recurring",
      intervalHours: 4,
    });
    expect(fetch).toHaveBeenCalledWith(
      "https://example.test/settings?specialist_id=default",
      expect.objectContaining({ method: "PUT" }),
    );
  });
});
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd web
npm test -- --run src/api/settings.test.ts
```

- [ ] **Step 3: Implement client, proxy, page**

Vite proxy:

```ts
"/api/settings": {
  target: "http://127.0.0.1:8088",
  changeOrigin: true,
  rewrite: (path) => path.replace(/^\/api\/settings/, "/settings"),
},
```

`.env.example`: `VITE_SETTINGS_URL=/api/settings`

`SettingsPage`:
- On mount: `fetchSettings(specialistId, token)` → fill controls + runs table
- **Save configuration** button → `saveSettings`
- Loading / error + retry for load
- Remove “Local only until config API exists” label when wired
- Keep Run triage as-is

- [ ] **Step 4: Run — expect PASS**

```bash
npm test -- --run src/api/settings.test.ts
```

- [ ] **Step 5: Commit** (skip unless user asked)

---

### Task 8: Web Drafts client + page

**Files:**
- Create: `web/src/api/drafts.ts`
- Create: `web/src/api/drafts.test.ts`
- Modify: `web/src/pages/DraftsPage.tsx`
- Modify: `web/vite.config.ts`
- Modify: `web/.env.example`

**Interfaces:**
- `fetchDrafts(specialistId, token?)`, `updateDraftStatus(id, status, opts?: { body?: string; token?: string })`

- [ ] **Step 1: Write failing client tests**

Create `web/src/api/drafts.test.ts`:

```typescript
import { fetchDrafts, updateDraftStatus, DraftsError } from "./drafts";

describe("drafts api", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_DRAFTS_URL", "https://example.test/drafts");
    vi.stubGlobal("fetch", vi.fn());
  });

  it("GETs with specialist_id and Authorization", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ items: [] }), { status: 200 }),
    );
    await fetchDrafts("default", "tok");
    expect(fetch).toHaveBeenCalledWith(
      "https://example.test/drafts?specialist_id=default",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ Authorization: "Bearer tok" }),
      }),
    );
  });

  it("PATCHes status", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "m1",
          subject: "Hi",
          to: "a@b.com",
          body: "Edited",
          status: "accepted",
          relatedQueueId: "m1",
        }),
        { status: 200 },
      ),
    );
    await updateDraftStatus("m1", "accepted", { body: "Edited", token: "tok" });
    expect(fetch).toHaveBeenCalledWith(
      "https://example.test/drafts/m1?specialist_id=default",
      expect.objectContaining({ method: "PATCH" }),
    );
  });

  it("throws DraftsError on 503", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "DATABASE_URL is not set" }), { status: 503 }),
    );
    await expect(fetchDrafts("default")).rejects.toBeInstanceOf(DraftsError);
  });
});
```

**Note:** `updateDraftStatus` must accept `specialistId` as well — prefer signature:

`updateDraftStatus(specialistId, id, status, opts?)` and adjust the test URL accordingly (`...?specialist_id=${specialistId}`).

- [ ] **Step 2: Run — expect FAIL**

```bash
npm test -- --run src/api/drafts.test.ts
```

- [ ] **Step 3: Implement**

Proxy:

```ts
"/api/drafts": {
  target: "http://127.0.0.1:8088",
  changeOrigin: true,
  rewrite: (path) => path.replace(/^\/api\/drafts/, "/drafts"),
},
```

`.env.example`: `VITE_DRAFTS_URL=/api/drafts`

`DraftsPage`:
- Load drafts on mount; loading / error+retry / empty
- Accept → `updateDraftStatus(specialistId, id, "accepted", { body: editBody if editing })`
- Discard → `updateDraftStatus(..., "discarded")`
- On success, remove item from local list (or refetch)
- **Send** → still `notifyNotConnected()` toast

- [ ] **Step 4: Run — expect PASS**

```bash
npm test -- --run src/api/drafts.test.ts
```

- [ ] **Step 5: Commit** (skip unless user asked)

---

### Task 9: Web Change lists + README

**Files:**
- Create: `web/src/api/changelists.ts`
- Create: `web/src/api/changelists.test.ts`
- Modify: `web/src/pages/ChangeListsPage.tsx`
- Modify: `web/vite.config.ts`
- Modify: `web/.env.example`
- Modify: `web/README.md`

**Interfaces:**
- `fetchChangeLists`, `updateChangeListStatus(id, "approved" | "needs_clarification", token?)`

- [ ] **Step 1: Write failing client tests**

Create `web/src/api/changelists.test.ts`:

```typescript
import { fetchChangeLists, updateChangeListStatus, ChangeListsError } from "./changelists";

describe("changelists api", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_CHANGELISTS_URL", "https://example.test/changelists");
    vi.stubGlobal("fetch", vi.fn());
  });

  it("GETs with specialist_id", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ items: [] }), { status: 200 }),
    );
    await fetchChangeLists("default", "tok");
    expect(fetch).toHaveBeenCalledWith(
      "https://example.test/changelists?specialist_id=default",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer tok" }),
      }),
    );
  });

  it("PATCHes approved", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({ id: "c1", clientId: "unknown", title: "DD", lines: [] }),
        { status: 200 },
      ),
    );
    await updateChangeListStatus("default", "c1", "approved", "tok");
    expect(fetch).toHaveBeenCalledWith(
      "https://example.test/changelists/c1?specialist_id=default",
      expect.objectContaining({ method: "PATCH" }),
    );
  });

  it("throws ChangeListsError on 503", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "DATABASE_URL is not set" }), { status: 503 }),
    );
    await expect(fetchChangeLists("default")).rejects.toBeInstanceOf(ChangeListsError);
  });
});
```

- [ ] **Step 2: Run — expect FAIL**

```bash
npm test -- --run src/api/changelists.test.ts
```

- [ ] **Step 3: Implement page + docs**

Proxy `/api/changelists` → `/changelists`. `.env.example`: `VITE_CHANGELISTS_URL=/api/changelists`.

`ChangeListsPage`: load on mount; Approve → `approved`; Request clarification → `needs_clarification`; remove from list on success. Line checkboxes stay local-only (not persisted).

`web/README.md`: add Settings / Drafts / Change lists rows to the wiring table and env docs.

- [ ] **Step 4: Run web + python smoke subset**

```bash
cd "c:\Users\Harshdeep\Downloads\Payroll - Agent - Plan"
.\.venv\Scripts\python.exe -m pytest tests/test_settings_http.py tests/test_drafts_http.py tests/test_changelists_http.py tests/test_drafts_mapping.py tests/test_changelists_mapping.py tests/test_email_repository_workbench.py tests/test_triage_workbench_persist.py -v
cd web
npm test -- --run src/api/settings.test.ts src/api/drafts.test.ts src/api/changelists.test.ts
```

Expected: all PASS

- [ ] **Step 5: Apply Neon migration** (manual / MCP when `DATABASE_URL` points at Neon)

```bash
# Using psql or Neon SQL editor:
# sql/002_add_hitl_status.sql
```

- [ ] **Step 6: Commit** (skip unless user asked)

---

## Spec coverage checklist

| Spec requirement | Task |
|---|---|
| `hitl_status` column | 1 |
| Drafts list filter pending | 1, 4, 8 |
| Change lists list filter pending | 1, 5, 9 |
| Accept / Discard | 4, 8 |
| Approve / needs_clarification | 5, 9 |
| Send stays toast | 8 |
| Settings GET/PUT + runs | 3, 7 |
| Triage draft + changelist shell | 6 |
| Empty lines OK | 2, 6 |
| No Snowflake | global |
| Mapping tests | 2 |
| 503 without DB for drafts/changelists | 4, 5 |
| Vite proxies + env | 7–9 |
| README | 9 |

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-25-workbench-connectivity.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks
2. **Inline Execution** — execute tasks in this session with checkpoints

Which approach?
