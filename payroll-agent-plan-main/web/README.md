# Payroll Specialist Web UI

Standalone React workbench for HRCs: Queue, Drafts, Q&A, Change lists, and Settings. Microsoft Entra sign-in can be disabled for local UI work (`VITE_AUTH_DISABLED=true`); that does **not** affect the Python backend Graph API credentials. Agent calls use the same Foundry Responses invoke endpoint as the Outlook add-in and `azd ai agent invoke`.

Design spec: [`docs/superpowers/specs/2026-09-23-payroll-specialist-ui-design.md`](../docs/superpowers/specs/2026-09-23-payroll-specialist-ui-design.md).

## Prerequisites

- Node.js 20+ and npm
- Microsoft Entra app registration (SPA) for specialist sign-in
- Foundry Hosted Agent deployed or running locally (`src/payroll_specialist/` — see root [README](../README.md))

## Install

```powershell
cd web
npm install
copy .env.example .env
# Edit .env — see Environment below
```

## Environment

Copy `web/.env.example` to `web/.env`. All client variables use the `VITE_` prefix (Vite exposes only these at build time).

| Variable | Purpose |
|---|---|
| `VITE_AUTH_DISABLED` | `false` for real Entra sign-in (required for real workbench use). `true` only for automated UI tests. |
| `VITE_ENTRA_CLIENT_ID` | Entra app (client) ID for the SPA (required only when auth is enabled) |
| `VITE_ENTRA_TENANT_ID` | Directory tenant ID, or `common` for multi-tenant |
| `VITE_ENTRA_REDIRECT_URI` | SPA redirect URI — default `http://localhost:5173` for local dev |
| `VITE_ENTRA_API_SCOPE` | Optional API scope for Foundry invoke; omit to use `openid` + `profile` + `email` |

Run triage acquires a separate **Graph** token (`Mail.Read`) and sends it as `Authorization: Bearer …` so the Python host can call `/me/messages` (delegated). Entra app registration must allow delegated `Mail.Read` for the SPA.
| `VITE_FOUNDRY_INVOKE_URL` | Foundry Responses invoke URL for the payroll specialist agent |
| `VITE_QA_INVOKE_URL` | Standalone Q&A agent (`POST /qa`) |
| `VITE_QUEUE_URL` | Neon open queue (`GET /queue`) |
| `VITE_SETTINGS_URL` | Triage config + run history (`GET/PUT /settings`) |
| `VITE_DRAFTS_URL` | Neon pending drafts (`GET/PATCH /drafts`) |
| `VITE_CHANGELISTS_URL` | Neon pending change lists (`GET/PATCH /changelists`) |

### Entra redirect URI

In the Entra app registration:

1. **Authentication** → **Platform configurations** → add **Single-page application**.
2. Register the same URI as `VITE_ENTRA_REDIRECT_URI` (e.g. `http://localhost:5173` for `npm run dev`).
3. Enable **Access tokens** and **ID tokens** under implicit grant if your tenant requires them for MSAL popup/silent flows.

The specialist ID sent to triage is derived from the signed-in account (`preferred_username`, `oid`, or `username`).

### Foundry invoke URL

`VITE_FOUNDRY_INVOKE_URL` is the POST endpoint that accepts `{ "input": "<message>" }` and returns the agent response body. It is the same contract as:

- Outlook add-in (`outlook_addin/taskpane.html`)
- Local/docs `FOUNDRY_AGENT_INVOKE_URL`

**Local default:** set `VITE_FOUNDRY_INVOKE_URL=/api/foundry`. Vite proxies that path to `http://127.0.0.1:8088/responses` (see `vite.config.ts`). Start the agent first:

```powershell
# from repo root
.\.venv\Scripts\python.exe src\payroll_specialist\main.py
# or: azd ai agent run
```

Then restart Vite (`cd web; npm run dev`) so env + proxy reload.

**Deployed:** replace with the real Foundry invoke URL from `azd deploy` / portal (and update root `FOUNDRY_AGENT_INVOKE_URL` to match).

### Q&A invoke URL

`VITE_QA_INVOKE_URL` targets the **standalone Q&A agent** (`POST /qa`), not the triage Responses path.

**Local default:** `/api/qa` → Vite proxies to `http://127.0.0.1:8088/qa`.

Body: `{ "messages": [{ "role": "user"|"assistant", "content": "..." }, ...] }`  
Response: `{ "answer": "...", "sources": [{ "label": "...", "detail": "..." }] }`

When unset, Q&A shows a config error and does **not** fall back to Foundry triage. When Foundry URL is unset, **Run triage** shows “Configure Foundry URL”.

### Queue URL

`VITE_QUEUE_URL` targets **`GET /queue`** (Neon `email_processing` open items). No blob/Graph fallback — missing `DATABASE_URL` on the host returns 503.

**Local default:** `/api/queue` → Vite proxies to `http://127.0.0.1:8088/queue?specialist_id=…`.

Optional `VITE_QUEUE_MAILBOX` (e.g. `payroll@peoservices.com`) is sent as `mailbox=` so local specialist `default` can list Neon rows keyed by a real `payroll_specialist_email`.

### Settings / Drafts / Change lists

| Variable | Host route | Notes |
|---|---|---|
| `VITE_SETTINGS_URL` | `GET/PUT /settings` | Triage store config + run history (no Neon required) |
| `VITE_DRAFTS_URL` | `GET/PATCH /drafts` | Neon pending drafts; Accept/Discard write `hitl_status` |
| `VITE_CHANGELISTS_URL` | `GET/PATCH /changelists` | Neon pending changelists; Approve / Request clarification |

**Local defaults:** `/api/settings`, `/api/drafts`, `/api/changelists` → Vite proxies to `:8088`.

Draft **Send** remains toast-only (no Graph send yet).

## Run locally

```powershell
cd web
npm run dev
```

Open the URL Vite prints (default `http://localhost:5173`). Sign in, then navigate all five areas: Queue, Drafts, Q&A, Change lists, Settings.

## How the UI maps to the agent

| UI action | Client | Payload | Agent path |
|---|---|---|---|
| **Q&A** composer | `src/api/qa.ts` → `VITE_QA_INVOKE_URL` | `{ messages: [...] }` full chat history | Standalone Q&A agent (`POST /qa`) + Cortex MCP |
| **Queue** list | `src/api/queue.ts` → `VITE_QUEUE_URL` | `GET ?specialist_id=` | Neon `email_processing` open categorized rows |
| **Drafts** list / Accept / Discard | `src/api/drafts.ts` → `VITE_DRAFTS_URL` | `GET` / `PATCH { status }` | Neon drafted rows + `hitl_status` |
| **Change lists** / Approve | `src/api/changelists.ts` → `VITE_CHANGELISTS_URL` | `GET` / `PATCH { status }` | Neon changelist rows + `hitl_status` |
| **Settings** load / save | `src/api/settings.ts` → `VITE_SETTINGS_URL` | `GET` / `PUT` config | Triage store config + run history |
| **Run triage** (header or Settings) | `src/api/foundry.ts` → `VITE_FOUNDRY_INVOKE_URL` | `TRIAGE_RUN specialist_id=<specialistId>` | Triage graph: classify + Neon upsert |

- Q&A: `QaPage` calls `invokeQaChat(messages, accessToken)` on send (does not use Foundry triage invoke).
- Queue: `QueuePage` calls `fetchQueue(specialistId, token)` on load / refresh.
- Triage: `runTriage(specialistId, token)` builds `TRIAGE_RUN specialist_id=...` via `triageRunInput()` and calls Foundry.
- Optional `Authorization: Bearer <token>` is attached when MSAL provides an access token.

Drafts and Change lists show empty/placeholder states until those APIs are wired — no fixture rows.

## Wire order (recommended)

Match the design spec when connecting features to live data:

1. Entra login → bearer token on requests
2. Q&A chat → `POST /qa` with full `messages` history → render `answer` + `sources`
3. Run triage → `TRIAGE_RUN specialist_id=...` (writes Neon queue/draft/changelist rows when `DATABASE_URL` is set)
4. Queue list/detail → `GET /queue` (Neon) — wired
5. Drafts HITL → `GET/PATCH /drafts` — wired (Send still toast)
6. Change lists → `GET/PATCH /changelists` — wired (lines may be empty)
7. Settings persist → `GET/PUT /settings` — wired

## Scripts

| Command | Purpose |
|---|---|
| `npm run dev` | Vite dev server with HMR |
| `npm run build` | Typecheck + production bundle (`dist/`) |
| `npm test` | Vitest unit tests |
| `npm run preview` | Serve production build locally |
| `npm run lint` | Oxlint |

## Project layout

```text
web/
  src/
    auth/       MSAL config, AuthGate, useSpecialist
    api/        foundry.ts, triage.ts
    layouts/    AppShell (nav + Run triage)
    pages/      Queue, Drafts, Qa, ChangeLists, Settings
    components/ shared UI (MasterDetail, EmptyState, …)
    styles/     tokens, global, grain
```
