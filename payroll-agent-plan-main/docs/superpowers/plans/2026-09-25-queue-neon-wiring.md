# Queue Neon Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire Queue list + detail to Neon `email_processing` via `GET /queue` (no blob/Graph fallback), with triage writing categorized rows and a required mapping unit test.

**Architecture:** During `TRIAGE_RUN`, upsert + classify each succeeded email into Neon. Mount Starlette `GET /queue` beside `POST /qa`. Map rows to `QueueItem` JSON. Web `QueuePage` loads via `VITE_QUEUE_URL` (Vite proxies `/api/queue` → `:8088/queue`). Actions stay “Not connected yet.”

**Tech Stack:** Python 3 + Starlette + SQLAlchemy (`EmailRepository`), Vite/React/TS, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-09-25-queue-neon-wiring-design.md`

## Global Constraints

- Neon only for Queue reads — no blob or Graph fallback; missing DB → HTTP 503.
- List + detail only; Open draft / Mark done / Adjust priority remain toast-only.
- Categories: `qa | changelist | todo | out_of_scope`.
- Priority map: `high→1`, `medium→3`, `low→5`, missing→3.
- Mapping unit test is required (do not ship without it).
- Commits: only when the user asks during execution; skip plan “Commit” steps unless explicitly requested.
- Do not introduce FastAPI or a second store for queue.

---

## File structure

```text
src/payroll_specialist/
  models.py              # add QueueItemResponse, QueueListResponse
  queue_mapping.py       # NEW — row/DTO → QueueItem dict (pure; unit-tested)
  queue_http.py          # NEW — GET /queue Starlette route
  db/repository.py       # list_open_queue + save_extracts (sub_content JSON)
  triage/orchestrator.py # Neon write on succeeded emails
  main.py                # mount_queue_route

tests/
  test_queue_mapping.py  # NEW — required mapping tests
  test_queue_http.py     # NEW — handler tests

web/
  src/api/queue.ts       # NEW
  src/api/queue.test.ts  # NEW
  src/pages/QueuePage.tsx
  vite.config.ts
  .env.example
  README.md (queue row in wiring table)
```

---

### Task 1: Queue mapping (TDD) — required

**Files:**
- Create: `src/payroll_specialist/queue_mapping.py`
- Create: `tests/test_queue_mapping.py`
- Modify: `src/payroll_specialist/models.py` (add response models used by mapper/HTTP)

**Interfaces:**
- Produces:
  - `map_priority_rate(priority_rate: str | None) -> int` → 1 | 3 | 5 (typed as int; values 1, 3, or 5)
  - `map_category(category_csv: str | None) -> str | None` → first allowed token or None
  - `body_excerpt(content: str | None, *, limit: int = 280) -> str | None`
  - `parse_extracts(sub_content: str | None) -> dict[str, str]`
  - `row_to_queue_item(row: Mapping[str, Any]) -> dict` with keys matching web `QueueItem`
  - Pydantic: `QueueItemResponse`, `QueueListResponse` in `models.py`

- [ ] **Step 1: Write the failing mapping tests**

Create `tests/test_queue_mapping.py`:

```python
from queue_mapping import (
    body_excerpt,
    map_category,
    map_priority_rate,
    parse_extracts,
    row_to_queue_item,
)


def test_map_priority_rate():
    assert map_priority_rate("high") == 1
    assert map_priority_rate("medium") == 3
    assert map_priority_rate("low") == 5
    assert map_priority_rate(None) == 3
    assert map_priority_rate("weird") == 3


def test_map_category_first_allowed():
    assert map_category("qa,changelist") == "qa"
    assert map_category("todo") == "todo"
    assert map_category("") is None
    assert map_category("unknown") is None


def test_body_excerpt_truncates():
    assert body_excerpt("x" * 300) == ("x" * 280)
    assert body_excerpt(None) is None
    assert body_excerpt("short") == "short"


def test_parse_extracts_json():
    assert parse_extracts('{"client_id":"C1","employee_id":"E9"}') == {
        "client_id": "C1",
        "employee_id": "E9",
    }
    assert parse_extracts(None) == {}
    assert parse_extracts("not-json") == {}


def test_row_to_queue_item_happy_path():
    item = row_to_queue_item(
        {
            "message_id": "m1",
            "subject": "Direct deposit change",
            "category": "changelist",
            "priority_rate": "high",
            "email_received_dttm": "2026-09-20T10:00:00+05:30",
            "content": "Please update bank account.",
            "sub_content": '{"client_id":"C1","employee_id":"E9"}',
        }
    )
    assert item["id"] == "m1"
    assert item["subject"] == "Direct deposit change"
    assert item["category"] == "changelist"
    assert item["priority"] == 1
    assert item["receivedAt"].startswith("2026-09-20")
    assert item["clientId"] == "C1"
    assert item["employeeId"] == "E9"
    assert item["bodyExcerpt"] == "Please update bank account."
    assert item["extracted"]["client_id"] == "C1"


def test_row_to_queue_item_fallbacks():
    item = row_to_queue_item(
        {
            "message_id": "m2",
            "subject": None,
            "category": None,
            "priority_rate": None,
            "email_received_dttm": None,
            "content": None,
            "sub_content": None,
        }
    )
    assert item["subject"] == "(no subject)"
    assert item["category"] == "todo"  # documented default when CSV empty
    assert item["priority"] == 3
    assert item.get("receivedAt")  # non-empty ISO fallback (e.g. epoch or now — pick one in impl)
    assert item.get("clientId") is None
```

**Implementer rule:** If category CSV is empty/invalid, `row_to_queue_item` sets `"todo"` and documents that in the function docstring. List API still filters `is_categorized=true`, so this is defensive only. For missing `email_received_dttm`, use ISO string `"1970-01-01T00:00:00+00:00"` so the UI never gets an empty timestamp.

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd "c:\Users\Harshdeep\Downloads\Payroll - Agent - Plan"
.\.venv\Scripts\python.exe -m pytest tests/test_queue_mapping.py -v
```

Expected: FAIL (import / not found)

- [ ] **Step 3: Implement mapping + models**

Add to `models.py`:

```python
class QueueItemResponse(BaseModel):
    id: str
    subject: str
    category: Literal["qa", "changelist", "todo", "out_of_scope"]
    priority: Literal[1, 2, 3, 4, 5]
    receivedAt: str
    clientId: str | None = None
    employeeId: str | None = None
    bodyExcerpt: str | None = None
    extracted: dict[str, str] | None = None


class QueueListResponse(BaseModel):
    items: list[QueueItemResponse]
```

Create `queue_mapping.py` implementing the functions above. `row_to_queue_item` must return camelCase keys matching the web type. For `email_received_dttm` that is a `datetime`, use `.isoformat()`. If category missing after parse, use `"todo"` (document in docstring).

- [ ] **Step 4: Run tests — expect PASS**

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_queue_mapping.py -v
```

Expected: PASS

- [ ] **Step 5: Commit** (skip unless user asked)

```bash
git add src/payroll_specialist/queue_mapping.py src/payroll_specialist/models.py tests/test_queue_mapping.py
git commit -m "feat: add Neon-to-QueueItem mapping with unit tests"
```

---

### Task 2: Repository — list open queue + save extracts

**Files:**
- Modify: `src/payroll_specialist/db/repository.py`
- Create: `tests/test_email_repository_queue.py` (use SQLite or skip if project has no in-memory DB pattern — prefer mocking session / test with real Neon only if `DATABASE_URL` in env; otherwise unit-test list query building via a thin pure helper)

**Preferred approach (no live Neon required):** add methods that are easy to call from HTTP with a fake repo in tests. Repository methods:

```python
def save_extracts(self, *, message_id: str, extracts: dict[str, Any]) -> None:
    """Persist extracts as JSON in sub_content (string values only)."""

def list_open_queue(self, *, specialist_mailbox: str, limit: int = 200) -> list[dict]:
    """
    Return dicts suitable for row_to_queue_item:
    message_id, subject, category, priority_rate, email_received_dttm,
    content, sub_content
    Filter: is_categorized True, is_processed False,
    payroll_specialist_email contains specialist_mailbox (case-insensitive).
    Order: priority_rate high first, then email_received_dttm desc.
    """
```

**Interfaces:**
- Consumes: existing `EmailProcessing` model, `now_ist`
- Produces: `save_extracts`, `list_open_queue` as above

- [ ] **Step 1: Write failing tests for save_extracts + list filter logic**

If full DB tests are heavy, test a pure SQL/filter helper OR use SQLite with `create_all`. Minimal test file:

```python
# tests/test_email_repository_queue.py
# Use sqlalchemy create_engine("sqlite:///:memory:") ONLY if ISTDateTime works on SQLite;
# otherwise mock Session and assert methods call expected filters.
```

Concrete minimal path: add `tests/test_email_repository_queue.py` that mocks `session_factory` and verifies `list_open_queue` returns mapped field dicts from fake scalars. Keep it short.

- [ ] **Step 2: Run — expect FAIL**

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_email_repository_queue.py -v
```

- [ ] **Step 3: Implement `save_extracts` and `list_open_queue`**

Priority ordering in SQL (Postgres):

```python
from sqlalchemy import case

priority_order = case(
    (EmailProcessing.priority_rate == "high", 1),
    (EmailProcessing.priority_rate == "medium", 2),
    (EmailProcessing.priority_rate == "low", 3),
    else_=2,
)
```

Filter mailbox with `func.lower(EmailProcessing.payroll_specialist_email).like(f"%{mailbox.lower()}%")`.

`save_extracts`: load row, set `sub_content = json.dumps({k: str(v) for k,v in extracts.items() if v is not None})`, commit. Raise `EmailNotFoundError` if missing.

- [ ] **Step 4: Run — expect PASS**

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_email_repository_queue.py -v
```

- [ ] **Step 5: Commit** (skip unless user asked)

---

### Task 3: `GET /queue` HTTP handler (TDD)

**Files:**
- Create: `src/payroll_specialist/queue_http.py`
- Create: `tests/test_queue_http.py`
- Modify: `src/payroll_specialist/main.py`

**Interfaces:**
- Consumes: `row_to_queue_item`, `QueueListResponse`, injectable `list_fn(specialist_id: str) -> list[dict]`
- Produces: `make_queue_route(list_fn=...)`, `mount_queue_route(app, list_fn=...)`

Default `list_fn` behavior when not injected:

1. Resolve specialist mailbox from triage store config: `get_triage_store().get_config(specialist_id)` → `mailbox_id` (or specialist_id if that is the mailbox email).
2. If `DATABASE_URL` missing / `get_email_repository()` raises → raise a typed error the route maps to 503.
3. `repo.list_open_queue(specialist_mailbox=mailbox)` → map each with `row_to_queue_item`.

- [ ] **Step 1: Write failing handler tests** (mirror `tests/test_qa_http.py`)

```python
import json
import pytest
from starlette.requests import Request
from queue_http import make_queue_route


def _request(query: str = b"specialist_id=default") -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/queue",
        "raw_path": b"/queue",
        "query_string": query,
        "headers": [],
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 8088),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


@pytest.mark.asyncio
async def test_queue_400_missing_specialist():
    route = make_queue_route(list_fn=lambda _sid: [])
    resp = await route(_request(b""))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_queue_200_items():
    def list_fn(sid: str):
        assert sid == "default"
        return [
            {
                "message_id": "m1",
                "subject": "Pay question",
                "category": "qa",
                "priority_rate": "medium",
                "email_received_dttm": "2026-09-20T10:00:00+05:30",
                "content": "Why lower?",
                "sub_content": None,
            }
        ]

    route = make_queue_route(list_fn=list_fn)
    resp = await route(_request(b"specialist_id=default"))
    assert resp.status_code == 200
    data = json.loads(resp.body)
    assert data["items"][0]["id"] == "m1"
    assert data["items"][0]["category"] == "qa"
    assert data["items"][0]["priority"] == 3


@pytest.mark.asyncio
async def test_queue_503_when_list_fn_raises_db():
    def boom(_sid: str):
        raise RuntimeError("DATABASE_URL is not set")

    route = make_queue_route(list_fn=boom)
    resp = await route(_request(b"specialist_id=default"))
    assert resp.status_code == 503
    assert "detail" in json.loads(resp.body)
```

- [ ] **Step 2: Run — expect FAIL**

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_queue_http.py -v
```

- [ ] **Step 3: Implement `queue_http.py` and mount in `main.py`**

```python
# queue_http.py sketch
def make_queue_route(list_fn=None):
    async def queue_route(request: Request) -> Response:
        specialist_id = (request.query_params.get("specialist_id") or "").strip()
        if not specialist_id:
            return JSONResponse({"detail": "specialist_id is required"}, status_code=400)
        try:
            rows = list_fn(specialist_id) if list_fn else default_list_queue(specialist_id)
            items = [row_to_queue_item(r) for r in rows]
            # drop rows with no category if any
            return JSONResponse(QueueListResponse(items=items).model_dump(), status_code=200)
        except Exception as exc:
            logger.exception("GET /queue failed")
            return JSONResponse({"detail": str(exc)}, status_code=503)
    return queue_route


def mount_queue_route(app, list_fn=None):
    app.add_route("/queue", make_queue_route(list_fn=list_fn), methods=["GET"])
```

In `main.py`, after `mount_qa_route(server.app)`:

```python
from queue_http import mount_queue_route
mount_queue_route(server.app)
logger.info("Mounted queue API at GET /queue")
```

(Both hosting import branches.)

- [ ] **Step 4: Run — expect PASS**

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_queue_http.py tests/test_queue_mapping.py -v
```

- [ ] **Step 5: Commit** (skip unless user asked)

---

### Task 4: Triage orchestrator → Neon write

**Files:**
- Modify: `src/payroll_specialist/triage/orchestrator.py`
- Modify: `tests/test_triage_full_flow.py` (or add `tests/test_triage_neon_persist.py`)

**Interfaces:**
- Consumes: `IngestedEmailInput`, `EmailRepository.upsert_ingested_email`, `save_classification`, `save_extracts`
- Optional injectable `email_repo` on `TriageOrchestrator` for tests (default `get_email_repository()` when `DATABASE_URL` set)

**Behavior on each succeeded email (after classification payload known):**

1. Build `IngestedEmailInput` from `MailMessage` + specialist mailbox as `recipients=[mailbox_id]`.
2. `upsert_ingested_email`.
3. `save_classification(email_id=..., categories=[category], priority="medium")` (or `"high"`/`"low"` if triage later exposes score — default medium for this slice).
4. `save_extracts` with non-null extract keys from triage dict.
5. If any Neon step raises: log, append/update result `status: "failed"`, `error: str(exc)` — do not mark processed for that message if ingest never completed; if already `mark_processed`, leave as-is but result status failed for visibility.

**Important:** If `DATABASE_URL` is not set, orchestrator should **fail the Neon write path with a clear error on succeeded emails** (per no-fallback). Spec: Queue requires DB. Options locked by product: either (a) triage run fails open-queue persistence when DB missing, or (b) triage continues but Queue stays empty/error. Spec says mark result failed on Neon write failure — implement that: catch, set result status failed, continue other emails. Entire run can still complete with partial failures.

- [ ] **Step 1: Write failing test with fake email_repo**

```python
class FakeEmailRepo:
    def __init__(self):
        self.upserts = []
        self.classifications = []
        self.extracts = []

    def upsert_ingested_email(self, *, message):
        self.upserts.append(message)
        return "inserted"

    def save_classification(self, *, email_id, categories, priority="medium"):
        self.classifications.append((email_id, categories, priority))

    def save_extracts(self, *, message_id, extracts):
        self.extracts.append((message_id, extracts))
```

Drive a minimal orchestrator run with one mock message and assert upsert + classify + extracts called.

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Wire orchestrator**

Parse `received_at` to datetime for `IngestedEmailInput`. Sender: `msg.from_address or "unknown@invalid"`.

- [ ] **Step 4: Run triage + mapping + http tests — expect PASS**

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_queue_mapping.py tests/test_queue_http.py tests/test_triage_neon_persist.py -v
```

- [ ] **Step 5: Commit** (skip unless user asked)

---

### Task 5: Web client + QueuePage load

**Files:**
- Create: `web/src/api/queue.ts`
- Create: `web/src/api/queue.test.ts`
- Modify: `web/src/pages/QueuePage.tsx`
- Modify: `web/vite.config.ts`
- Modify: `web/.env.example`
- Modify: `web/README.md` (add Queue row to wiring table)
- Modify: `web/src/vite-env.d.ts` if env types listed there

**Interfaces:**
- Produces: `fetchQueue(specialistId: string, token?: string): Promise<QueueItem[]>`, `QueueError` class

- [ ] **Step 1: Write failing `queue.test.ts`**

```typescript
import { fetchQueue, QueueError } from "./queue";

describe("fetchQueue", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_QUEUE_URL", "https://example.test/queue");
    vi.stubGlobal("fetch", vi.fn());
  });

  it("GETs with specialist_id and Authorization", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ items: [] }), { status: 200 }),
    );
    await fetchQueue("default", "tok");
    expect(fetch).toHaveBeenCalledWith(
      "https://example.test/queue?specialist_id=default",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ Authorization: "Bearer tok" }),
      }),
    );
  });

  it("throws QueueError on 503", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "DATABASE_URL is not set" }), { status: 503 }),
    );
    await expect(fetchQueue("default")).rejects.toBeInstanceOf(QueueError);
  });
});
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd web
npm test -- --run src/api/queue.test.ts
```

- [ ] **Step 3: Implement `queue.ts`, proxy, env, QueuePage**

`fetchQueue`: require `VITE_QUEUE_URL`; GET; parse `{ items }`; on !ok throw `QueueError`.

Vite proxy:

```ts
"/api/queue": {
  target: "http://127.0.0.1:8088",
  changeOrigin: true,
  rewrite: (path) => path.replace(/^\/api\/queue/, "/queue"),
},
```

`.env.example`:

```
# Local: /api/queue (Vite proxies to http://127.0.0.1:8088/queue)
VITE_QUEUE_URL=/api/queue
```

`QueuePage` changes:
- On mount: `getAccessToken` + `fetchQueue(specialistId, token)`.
- States: `loading`, `error` (inline + Retry), `items` from server.
- Replace `useState<QueueItem[]>([])` constant with loaded items.
- Keep action toasts as-is.

- [ ] **Step 4: Run web tests**

```bash
cd web
npm test -- --run src/api/queue.test.ts
```

Expected: PASS

- [ ] **Step 5: Manual smoke**

1. Ensure `.env` has `DATABASE_URL` and web `.env` has `VITE_QUEUE_URL=/api/queue`.
2. Start agent: `.\.venv\Scripts\python.exe src\payroll_specialist\main.py`
3. Start web: `cd web; npm run dev`
4. Run triage from header; open Queue — items appear or clear empty/error.

- [ ] **Step 6: Commit** (skip unless user asked)

---

## Spec coverage checklist

| Spec requirement | Task |
|---|---|
| Neon only, no blob/Graph fallback | 3 (503), 5 (error UI) |
| Triage upsert + classify | 4 |
| Extracts for detail | 2 + 4 (`sub_content` JSON) |
| `GET /queue` | 3 |
| Mapping + required unit test | 1 |
| Handler tests | 3 |
| Web client + QueuePage | 5 |
| Actions still not connected | 5 (no change to action handlers) |
| Priority map high/medium/low | 1 |

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-25-queue-neon-wiring.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute tasks in this session with checkpoints  

Which approach?
