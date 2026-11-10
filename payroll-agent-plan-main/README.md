# LangGraph Payroll Specialist Engine (Phase 1)

Azure Foundry Hosted Agent that extends the payroll LangGraph workflow with Outlook triage (UC-001–010), four-way classification (`qa` | `changelist` | `todo` | `out_of_scope`), a routing agent for out-of-scope mail, Blob/local durable config, and agent + step-wise OpenTelemetry to Application Insights.

The original POC (`langgraph-agent-payroll-responses`) is left untouched.

## Architecture

- **Host:** Microsoft Foundry Hosted Agent — `ResponsesHostServer` on port 8088 (`azd deploy`), plus standalone `POST /qa` for the console Q&A agent.
- **Graph:** LangGraph `StateGraph` under `src/payroll_specialist/` — Foundry `/responses` is **TRIAGE_RUN only**; per-email classify lives in `triage/email_graph.py`; console Q&A is `POST /qa`.
- **Console Q&A:** `POST /qa` → standalone ReAct agent + Cortex MCP → `{ answer, sources }` (no classifier/drafter).
- **Triage path:** `TRIAGE_RUN` → load config → window → fetch mail → **skip processed** → **thread context** → **full per-email graph** (classify → QA / draft / route) → mark processed → summary.
- **Categories:** engine enum `qa | changelist | todo | out_of_scope` — see `docs/taxonomy-mapping.md`.
- **Recurring:** External Logic App / Timer only (see `deploy/recurring-invoke.sample.json`). No in-container APScheduler.

```text
Web Q&A console ──POST /qa──► Standalone Q&A agent (Cortex MCP)
Outlook / Timer / CLI ──Responses invoke──► Foundry Hosted Agent
                                              └── TRIAGE_RUN only → store + mailbox → per-email classify
                                              (free-form chat on /responses is rejected → use POST /qa)
```

## Project layout

```text
langgraph-payroll-specialist-engine/
  azure.yaml
  langgraph.json
  pyproject.toml
  deploy/recurring-invoke.sample.json
  outlook_addin/
  src/payroll_specialist/
    main.py                 # Foundry entry (ResponsesHostServer)
    graph.py                # compiles graph; exports `graph`
    state.py / models.py / prompts.py / telemetry.py / config.py
    nodes/                  # intake, classifier, qa, drafting, routing
    tools/snowflake_mcp.py
    triage/                 # orchestrator, window, mailbox, auth
    store/                  # local_store + blob_store
  tests/
```

## Environment

Copy `src/payroll_specialist/.env.example` to `.env` (repo root and/or package dir).

| Variable | Purpose |
|---|---|
| `FOUNDRY_PROJECT_ENDPOINT` | Foundry project endpoint |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | Model deployment |
| `AZURE_AI_API_KEY` | **LLM API key** (also accepts `FOUNDRY_API_KEY` / `AZURE_OPENAI_API_KEY`) — no `az login` |
| `mcp_config.json` | Cursor-style MCP server config (`mcp-remote` + `--static-oauth-client-info`) — primary Snowflake Cortex connection |
| `MCP_CONFIG_PATH` | Optional override path to the MCP JSON |
| `SNOWFLAKE_MCP_AUTH` | `oauth` (default, mcp-remote) or `pat` (Bearer programmatic access token) |
| `SNOWFLAKE_PAT` | Required when `SNOWFLAKE_MCP_AUTH=pat` (falls back to `SNOWFLAKE_OAUTH_TOKEN`) |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Trace export (Live Metrics suppressed) |
| `AZURE_STORAGE_CONNECTION_STRING` | Durable triage config/runs (omit → local filesystem store under `TRIAGE_LOCAL_STORE_PATH`) |
| `TRIAGE_BLOB_CONTAINER` | Blob container name |
| `DATABASE_URL` | **Required** for triage Neon persist / Queue / Drafts / Change lists |
| `GRAPH_AUTH_MODE` | `delegated` (default) uses the specialist’s Bearer `Mail.Read` token from Run triage — **no client secret**. `app` uses client credentials + secret. |
| `GRAPH_TENANT_ID` / `GRAPH_CLIENT_ID` | Required for Graph (delegated or app) |
| `GRAPH_CLIENT_SECRET` | Required only when `GRAPH_AUTH_MODE=app` |
| `GRAPH_MAILBOX_ALLOWLIST` | Comma-separated mailbox allow-list (empty = all allowed) |
| `DEFAULT_LOOKBACK_DAYS` / `DEFAULT_INTERVAL_HOURS` | UC-004 / UC-006 defaults (`2\|4\|24`) |

**Real-only runtime:** There is no demo Graph/Neon path. Missing Graph credentials or `DATABASE_URL` fails triage. Snowflake MCP missing fails tool load (unless `PAYROLL_MCP_OFFLINE=1` for unit tests/CI only).

## Local setup

```powershell
cd "c:\Users\Harshdeep\Downloads\Payroll - Agent - Plan"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r src\payroll_specialist\requirements.txt
# Fill .env: AZURE_AI_API_KEY + Snowflake (SNOWFLAKE_MCP_AUTH=oauth|pat)
```

### Unit tests (mocks injected in tests only — no runtime demo mode)

```powershell
.\.venv\Scripts\python.exe -m pytest tests -v
```

### Interactive CLI

```powershell
.\run_cli.ps1
# or:
.\.venv\Scripts\python.exe src\payroll_specialist\cli_tester.py
```

### Local Responses host

```powershell
azd ai agent run
# or:
.\.venv\Scripts\python.exe src\payroll_specialist\main.py
```

Invoke examples:

```powershell
# Triage only on Foundry Responses (/responses)
azd ai agent invoke --local "TRIAGE_RUN specialist_id=demo-specialist"
azd ai agent invoke --local '{"command":"triage","specialist_id":"demo-specialist"}'

# Q&A is a separate endpoint (POST /qa) — not Foundry chat invoke
# curl -X POST http://127.0.0.1:8088/qa -H "Content-Type: application/json" `
#   -d '{"messages":[{"role":"user","content":"Why was my August paycheck lower? EMP-1042"}]}'
```

## Deploy (Foundry)

```powershell
az login
azd auth login
azd deploy
azd ai agent invoke "TRIAGE_RUN specialist_id=default"
```

`azure.yaml` mirrors the POC: same Foundry project endpoint pattern, Live Metrics / QuickPulse disabled, App Insights connection for **traces only**.

## Telemetry

- Module: `telemetry.py`
- **Agent run** span per invoke: `run_id`, `specialist_id`, `mode`, `mailbox_id`, `email_count`, `status`
- **Step** spans: `intake`, `load_config`, `processing_window`, `retrieve_emails`, `classifier`, `qa_specialist`, `drafting_specialist`, `routing_agent`, `finalize_run`, tools
- **PII guard:** no email body/subject/full names in attributes
- Offline assertion: `tests/test_telemetry.py` (in-memory exporter)

App Insights example (KQL):

```kusto
dependencies
| where cloud_RoleName == "payroll-specialist-engine" or name startswith "step_" or name == "agent_run"
| project timestamp, name, duration, customDimensions
| order by timestamp desc
```

## Web UI

Standalone specialist workbench in [`web/`](web/) — Queue, Drafts, Q&A, Change lists, and Settings. Vite + React + TypeScript with Microsoft Entra ID (MSAL) sign-in.

- **Setup:** `cd web && npm install`, copy `web/.env.example` to `web/.env`, then `npm run dev`.
- **Agent calls:** Q&A posts chat history to the standalone `/qa` endpoint (`VITE_QA_INVOKE_URL`); **Run triage** sends `TRIAGE_RUN specialist_id=...` to the Foundry Responses invoke URL (`VITE_FOUNDRY_INVOKE_URL`).
- **Docs:** See [`web/README.md`](web/README.md) for Entra redirect URI, env vars, wire order, and scripts.

The Outlook add-in remains a thin triage trigger; the web app is the primary workbench surface.

## Outlook add-in (UC-003)

`outlook_addin/taskpane.html` POSTs `TRIAGE_RUN specialist_id=...` to the Foundry Responses invoke URL. Sideload `manifest.xml` after hosting the taskpane (update URLs for your environment).

## Recurring (UC-005 / UC-006)

1. Persist `mode=recurring` and `interval_hours` ∈ `{2,4,24}` in Blob/local specialist config.
2. Schedule an **external** Logic App / Timer (see `deploy/recurring-invoke.sample.json`) to invoke Foundry on that cadence with `TRIAGE_RUN specialist_id=...`.

## Categories & routing

| Category | Path |
|---|---|
| `qa` | QA specialist (Snowflake Cortex) → drafting |
| `changelist` / `todo` | drafting |
| `out_of_scope` | routing agent → internal department draft (`benefits` \| `tax` \| `workers_comp` \| `other`) |
