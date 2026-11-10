# Payroll Specialist Web UI — Design Spec

**Date:** 2026-09-23  
**Status:** Approved for planning  
**Source requirements:** `Requirement/Engage AI - Payroll Specialist - Use Case - Copy.xlsx`  
**Frontend skill:** `Skills/Frontend-Skill.md`

## 1. Goal

Ship a standalone specialist workbench so HRCs can triage payroll email work, review drafts, ask Q&A, review change lists, and manage triage settings — while the LangGraph / Foundry agent backend continues in parallel.

The Outlook add-in remains a thin “start triage” trigger. The web app is the primary experience.

## 2. Decisions (locked)

| Topic | Choice |
|---|---|
| Primary surface | Standalone web app |
| First slice | App shell with all main areas; polish **Queue** first |
| Stack | Vite + React + TypeScript |
| Auth | Microsoft Entra ID (MSAL) |
| Data | No mock API layer; UI ready first; wire Foundry/agent one feature at a time |
| Backend for now | Current setup only — Foundry `ResponsesHostServer` / agent invoke (not FastAPI) |
| Layout pattern | Master–detail workbench (Approach 1) |
| Nav areas | Queue · Drafts · Q&A · Change lists · Settings |
| Visual | Industrial precision workbench per Frontend-Skill |

## 3. Architecture

```text
Browser (web/)
  ├── MSAL (Entra) ──► access token
  ├── React Router shell (nav + header)
  └── api/foundry.ts ──► Foundry Responses / agent invoke
                            ├── chat / Q&A path (existing graph)
                            └── TRIAGE_RUN (existing triage path)

Outlook add-in (unchanged) ──► same TRIAGE_RUN invoke
Python backend (src/payroll_specialist/) ──► LangGraph + ResponsesHostServer
```

- **Location:** `web/` at repo root (sibling to `src/payroll_specialist/`).
- **Auth:** MSAL React; bearer token on every agent call. Specialist context (id, mailbox, display name) from token claims; extend when a profile command/endpoint exists.
- **API coupling:** Typed client modules against Foundry invoke. Empty / loading / error states until each capability is wired. No fixture JSON “mock backend.”
- **Out of scope for this phase:** FastAPI BFF, autonomous write-back to PRISMHR/iSolved, learning-from-edits (UC-028/064).

## 4. Screens & components

### 4.1 Shell

- Left rail nav: Queue, Drafts, Q&A, Change lists, Settings.
- Header: product name **Payroll Specialist** (strong brand signal), specialist identity, **Run triage** action.
- Auth gate: unauthenticated users see login only.

### 4.2 Queue (first polish — UC-026–028)

- Master–detail: prioritized list + selected item detail.
- List: priority, category (`qa` | `changelist` | `todo` | `out_of_scope`), subject, client/employee signals when present, received time.
- Filters: category, priority.
- Detail: subject/body excerpt, classification, extracted fields, actions (open related draft, adjust priority UI, mark done — wired when agent supports them).
- Empty state until queue data is available from the agent/store.

### 4.3 Drafts (UC-036–040)

- List of pending drafts; detail with Accept / Edit / Discard / Send (HITL).
- Body editor for edits before send.
- Empty state until draft persistence/list is available.

### 4.4 Q&A (UC-042–053)

- Full-height chat: message list + composer.
- Optional sources/citations panel when the agent returns them.
- **First real wire after auth:** composer → Foundry invoke → render assistant reply (existing QA graph path).

### 4.5 Change lists (UC-055–067)

- List of change sets (per client/conversation); detail with line items.
- Line-by-line review checkboxes; approve / request clarification actions (UI ready; wire later).
- No autonomous write-back (UC-059).

### 4.6 Settings (UC-004–008, 032)

- Lookback days, triage mode (manual vs recurring), interval (2h / 4h / 24h).
- Run history table when available.
- Run triage now (same invoke as header / Outlook add-in).
- Persist when config command/API exists; until then controls may be display-only or local-only (explicitly labeled).

## 5. Data flow & wiring order

1. Entra login → token on requests.
2. Q&A chat → Foundry Responses invoke with user message → render final assistant text (streaming can follow later).
3. Run triage → invoke `TRIAGE_RUN specialist_id=...` → toast / status from response when present.
4. Queue list/detail → wire when agent/store exposes triage results for UI.
5. Drafts HITL → wire when draft payloads are available.
6. Change lists → wire when change-list payloads are available.
7. Settings persist → wire when config load/save exists (blob/store already used by backend).

**Error handling**

- Auth failure → prompt re-login.
- Invoke timeout / 5xx → inline error + retry.
- Missing capability → empty state copy: “Not connected yet,” not fake rows.

## 6. Visual direction (`Skills/Frontend-Skill.md`)

**Concept:** Industrial precision workbench — a control room for deadlines and queues, not a soft SaaS dashboard.

| Element | Direction |
|---|---|
| Tone | Utilitarian / refined |
| Typography | Distinctive display + refined body; no Inter, Roboto, Arial, Space Grotesk |
| Color | CSS variables: deep ink slate, cool paper panels, one sharp amber accent for priority/CTA only; no purple-on-white gradients |
| Layout | Asymmetric shell — narrow rail, wide master–detail; Queue denser than Drafts; Q&A more open |
| Atmosphere | Subtle grain or fine grid in chrome; depth without clutter |
| Motion | Staggered page enter + purposeful queue-row hover (CSS and/or anime.js); no scattered micro-noise |
| Brand | Product name is a clear header signal; Queue first view is one composition (list + detail), not a widget dashboard |

## 7. Project layout (proposed)

```text
web/
  package.json
  vite.config.ts
  index.html
  src/
    main.tsx
    App.tsx
    auth/          # MSAL config + AuthGate
    api/           # foundry client, types
    layouts/       # AppShell
    pages/         # Queue, Drafts, Qa, ChangeLists, Settings
    components/    # shared UI primitives
    styles/        # tokens, global, grain
    types/         # domain types aligned with backend Category
```

Env (examples): `VITE_ENTRA_CLIENT_ID`, `VITE_ENTRA_TENANT_ID`, `VITE_ENTRA_REDIRECT_URI`, `VITE_FOUNDRY_INVOKE_URL`.

## 8. Testing

- Manual: login, navigate all five areas, empty states, Q&A invoke when configured, Run triage when configured.
- Unit (later): foundry client request shaping; priority sort helpers once queue data exists.
- No E2E required for the initial UI shell.

## 9. Success criteria

- Specialist can sign in with Entra and see the full workbench shell.
- Queue UI is the most complete interaction surface (filters, list, detail, empty/loading).
- Drafts, Q&A, Change lists, Settings are navigable and structurally complete.
- Q&A and Run triage can call the existing Foundry agent when env is set.
- Visual identity matches the industrial workbench direction and Frontend-Skill constraints.
- Backend team can continue without depending on a mock UI API.

## 10. Non-goals (this phase)

- FastAPI or other BFF.
- Mock/fixture API server.
- Replacing or expanding the Outlook add-in beyond current triage trigger.
- Production hardening of Entra app registration docs beyond `.env.example` notes.
- Learning loops from queue/change-list edits (UC-028, UC-064).
