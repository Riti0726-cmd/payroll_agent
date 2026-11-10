# Payroll Specialist Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Vite + React + TypeScript specialist workbench (`web/`) with Entra auth, industrial visual design, full nav shell (Queue · Drafts · Q&A · Change lists · Settings), polished Queue UI, and Foundry agent invoke wired for Q&A + Run triage.

**Architecture:** SPA in `web/` calls existing Foundry Responses invoke (`POST` with `{ input }`) using MSAL bearer tokens — same pattern as `outlook_addin/taskpane.html`. No FastAPI BFF, no mock API. Unwired areas show empty/loading/error states only.

**Tech Stack:** Vite 6, React 19, TypeScript 5, React Router 7, `@azure/msal-browser` + `@azure/msal-react`, Vitest + Testing Library, anime.js, CSS modules / global CSS variables (no Inter/Roboto/Arial/Space Grotesk).

**Spec:** `docs/superpowers/specs/2026-09-23-payroll-specialist-ui-design.md`  
**Frontend skill:** `Skills/Frontend-Skill.md`

## Global Constraints

- App lives under `web/` at repo root; do not modify Python agent behavior except docs/env notes if needed.
- No mock/fixture API server; no fake queue/draft rows.
- Foundry invoke body shape: `{ "input": string }` (match Outlook add-in).
- Categories align with backend: `qa | changelist | todo | out_of_scope`.
- Visual: industrial workbench — ink slate + paper panels + amber accent only; subtle grain; staggered enter motion.
- Fonts: distinctive Google Fonts pair (use **Syne** display + **IBM Plex Sans** body); never Inter/Roboto/Arial/Space Grotesk.
- Q&A v1: final (non-streaming) assistant text only.
- Commits: only when the user asks during execution; skip plan “Commit” steps unless explicitly requested.

---

## File structure (create)

```text
web/
  package.json
  vite.config.ts
  tsconfig.json
  tsconfig.app.json
  tsconfig.node.json
  index.html
  .env.example
  README.md
  src/
    main.tsx
    App.tsx
    vite-env.d.ts
    auth/
      msalConfig.ts
      AuthGate.tsx
      useSpecialist.ts
    api/
      foundry.ts
      foundry.test.ts
    types/
      domain.ts
    layouts/
      AppShell.tsx
      AppShell.module.css
    pages/
      QueuePage.tsx
      QueuePage.module.css
      DraftsPage.tsx
      DraftsPage.module.css
      QaPage.tsx
      QaPage.module.css
      ChangeListsPage.tsx
      ChangeListsPage.module.css
      SettingsPage.tsx
      SettingsPage.module.css
      LoginPage.tsx
      LoginPage.module.css
    components/
      EmptyState.tsx
      EmptyState.module.css
      PriorityBadge.tsx
      CategoryChip.tsx
      MasterDetail.tsx
      MasterDetail.module.css
      Toast.tsx
    styles/
      tokens.css
      global.css
      grain.css
    lib/
      queueSort.ts
      queueSort.test.ts
      animateEnter.ts
```

---

### Task 1: Scaffold Vite React TypeScript app

**Files:**
- Create: `web/package.json`, `web/vite.config.ts`, `web/tsconfig*.json`, `web/index.html`, `web/src/main.tsx`, `web/src/App.tsx`, `web/src/vite-env.d.ts`, `web/README.md`

**Interfaces:**
- Consumes: none
- Produces: runnable `npm run dev` / `npm run build` / `npm test` scripts

- [ ] **Step 1: Scaffold with Vite**

From repo root:

```powershell
npm create vite@latest web -- --template react-ts
cd web
npm install
npm install react-router-dom @azure/msal-browser @azure/msal-react animejs
npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom @types/animejs
```

- [ ] **Step 2: Configure Vitest in `vite.config.ts`**

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
  },
});
```

Create `web/src/test/setup.ts`:

```ts
import "@testing-library/jest-dom";
```

Add to `package.json` scripts: `"test": "vitest run"`, `"test:watch": "vitest"`.

- [ ] **Step 3: Replace default App with placeholder**

`web/src/App.tsx`:

```tsx
export default function App() {
  return <main>Payroll Specialist</main>;
}
```

- [ ] **Step 4: Verify build**

Run: `cd web; npm run build`  
Expected: success, no TS errors.

- [ ] **Step 5: Commit** (skip unless user asks)

```bash
git add web
git commit -m "chore(web): scaffold Vite React TypeScript app"
```

---

### Task 2: Design tokens and global industrial styles

**Files:**
- Create: `web/src/styles/tokens.css`, `web/src/styles/global.css`, `web/src/styles/grain.css`
- Modify: `web/index.html` (font links), `web/src/main.tsx` (import styles)

**Interfaces:**
- Consumes: none
- Produces: CSS variables `--ink`, `--paper`, `--amber`, `--muted`, `--rail`, `--line`, `--danger`, fonts Syne + IBM Plex Sans

- [ ] **Step 1: Add Google Fonts to `index.html`**

```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link
  href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Syne:wght@600;700;800&display=swap"
  rel="stylesheet"
/>
```

- [ ] **Step 2: Write `tokens.css`**

```css
:root {
  --ink: #0e1518;
  --ink-elevated: #162024;
  --paper: #eef2f1;
  --paper-2: #e2e8e6;
  --amber: #e8a317;
  --amber-dim: #b87d0c;
  --muted: #6b7a80;
  --rail: #0a1012;
  --line: rgba(14, 21, 24, 0.12);
  --danger: #c23b22;
  --ok: #1f7a4c;
  --font-display: "Syne", sans-serif;
  --font-body: "IBM Plex Sans", sans-serif;
  --radius: 2px;
  --shadow-panel: 0 1px 0 rgba(255, 255, 255, 0.04), 0 12px 40px rgba(0, 0, 0, 0.35);
}
```

- [ ] **Step 3: Write `global.css` + `grain.css`**

`global.css`: reset, `body` on `--ink` / `--font-body`, headings on `--font-display`, focus rings using `--amber`, button base styles.

`grain.css`: fixed full-viewport `::before` pseudo on `body` with subtle noise SVG/data-URI opacity ~0.04, `pointer-events: none`.

- [ ] **Step 4: Import in `main.tsx`**

```tsx
import "./styles/tokens.css";
import "./styles/global.css";
import "./styles/grain.css";
```

- [ ] **Step 5: Visual check**

Run: `cd web; npm run dev`  
Expected: dark ink page, Syne title if present, faint grain — not purple, not Inter.

---

### Task 3: Domain types + queue sort helper (TDD)

**Files:**
- Create: `web/src/types/domain.ts`, `web/src/lib/queueSort.ts`, `web/src/lib/queueSort.test.ts`

**Interfaces:**
- Consumes: none
- Produces:
  - `export type Category = "qa" | "changelist" | "todo" | "out_of_scope"`
  - `export type Priority = 1 | 2 | 3 | 4 | 5` (1 = highest)
  - `export interface QueueItem { id: string; subject: string; category: Category; priority: Priority; receivedAt: string; clientId?: string; employeeId?: string; bodyExcerpt?: string; extracted?: Record<string, string>; }`
  - `export interface DraftItem { id: string; subject: string; to: string; body: string; status: "pending" | "accepted" | "discarded" | "sent"; relatedQueueId?: string; }`
  - `export interface ChangeListItem { id: string; clientId: string; title: string; lines: { id: string; field: string; from?: string; to?: string; reviewed: boolean }[]; }`
  - `export interface ChatMessage { id: string; role: "user" | "assistant"; content: string; sources?: string[]; }`
  - `export function sortQueueItems(items: QueueItem[]): QueueItem[]` — sort by `priority` asc, then `receivedAt` asc

- [ ] **Step 1: Write failing test**

```ts
// web/src/lib/queueSort.test.ts
import { describe, it, expect } from "vitest";
import { sortQueueItems } from "./queueSort";
import type { QueueItem } from "../types/domain";

const base = (over: Partial<QueueItem>): QueueItem => ({
  id: "1",
  subject: "s",
  category: "todo",
  priority: 3,
  receivedAt: "2026-09-23T10:00:00Z",
  ...over,
});

describe("sortQueueItems", () => {
  it("orders by priority then receivedAt", () => {
    const items = [
      base({ id: "a", priority: 3, receivedAt: "2026-09-23T12:00:00Z" }),
      base({ id: "b", priority: 1, receivedAt: "2026-09-23T11:00:00Z" }),
      base({ id: "c", priority: 1, receivedAt: "2026-09-23T09:00:00Z" }),
    ];
    expect(sortQueueItems(items).map((i) => i.id)).toEqual(["c", "b", "a"]);
  });
});
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `cd web; npm test -- src/lib/queueSort.test.ts`  
Expected: FAIL (module/function missing).

- [ ] **Step 3: Implement types + sort**

```ts
// web/src/types/domain.ts — as listed in Interfaces

// web/src/lib/queueSort.ts
import type { QueueItem } from "../types/domain";

export function sortQueueItems(items: QueueItem[]): QueueItem[] {
  return [...items].sort((a, b) => {
    if (a.priority !== b.priority) return a.priority - b.priority;
    return a.receivedAt.localeCompare(b.receivedAt);
  });
}
```

- [ ] **Step 4: Run test — expect PASS**

Run: `cd web; npm test -- src/lib/queueSort.test.ts`  
Expected: PASS.

---

### Task 4: Foundry invoke client (TDD)

**Files:**
- Create: `web/src/api/foundry.ts`, `web/src/api/foundry.test.ts`

**Interfaces:**
- Consumes: `import.meta.env.VITE_FOUNDRY_INVOKE_URL`
- Produces:
  - `export class FoundryError extends Error { status: number; body: string }`
  - `export async function invokeFoundry(input: string, accessToken?: string): Promise<string>`
  - Request: `POST` JSON `{ input }`, headers `Content-Type: application/json` and optional `Authorization: Bearer ${accessToken}`
  - On non-OK: throw `FoundryError`
  - Returns response text (final, non-streaming)

- [ ] **Step 1: Write failing tests**

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { invokeFoundry, FoundryError } from "./foundry";

describe("invokeFoundry", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_FOUNDRY_INVOKE_URL", "https://example.test/invoke");
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("POSTs { input } with bearer token", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => "hello",
    });
    vi.stubGlobal("fetch", fetchMock);

    const text = await invokeFoundry("Why was pay lower?", "tok-1");
    expect(text).toBe("hello");
    expect(fetchMock).toHaveBeenCalledWith(
      "https://example.test/invoke",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          Authorization: "Bearer tok-1",
        }),
        body: JSON.stringify({ input: "Why was pay lower?" }),
      }),
    );
  });

  it("throws FoundryError on non-OK", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        text: async () => "boom",
      }),
    );
    await expect(invokeFoundry("x")).rejects.toBeInstanceOf(FoundryError);
  });

  it("throws if VITE_FOUNDRY_INVOKE_URL missing", async () => {
    vi.stubEnv("VITE_FOUNDRY_INVOKE_URL", "");
    await expect(invokeFoundry("x")).rejects.toThrow(/VITE_FOUNDRY_INVOKE_URL/);
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd web; npm test -- src/api/foundry.test.ts`  
Expected: FAIL.

- [ ] **Step 3: Implement `foundry.ts`**

```ts
export class FoundryError extends Error {
  status: number;
  body: string;
  constructor(status: number, body: string) {
    super(`Foundry invoke failed (${status})`);
    this.status = status;
    this.body = body;
  }
}

export async function invokeFoundry(
  input: string,
  accessToken?: string,
): Promise<string> {
  const url = import.meta.env.VITE_FOUNDRY_INVOKE_URL as string | undefined;
  if (!url) throw new Error("VITE_FOUNDRY_INVOKE_URL is not set");

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  const resp = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify({ input }),
  });
  const body = await resp.text();
  if (!resp.ok) throw new FoundryError(resp.status, body);
  return body;
}

export function triageRunInput(specialistId: string): string {
  return `TRIAGE_RUN specialist_id=${specialistId}`;
}
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd web; npm test -- src/api/foundry.test.ts`  
Expected: PASS.

---

### Task 5: MSAL auth + specialist context

**Files:**
- Create: `web/src/auth/msalConfig.ts`, `web/src/auth/AuthGate.tsx`, `web/src/auth/useSpecialist.ts`, `web/src/pages/LoginPage.tsx`, `web/src/pages/LoginPage.module.css`
- Modify: `web/src/main.tsx`, `web/src/App.tsx`
- Create: `web/.env.example`

**Interfaces:**
- Consumes: env `VITE_ENTRA_CLIENT_ID`, `VITE_ENTRA_TENANT_ID`, `VITE_ENTRA_REDIRECT_URI`, `VITE_ENTRA_API_SCOPE` (optional; default `openid profile`)
- Produces:
  - `msalInstance` / `msalConfig`
  - `AuthGate` — children only when authenticated; else `LoginPage`
  - `useSpecialist(): { specialistId: string; displayName: string; getAccessToken: () => Promise<string | undefined> }`
  - `specialistId` from `preferred_username` or `oid` claim (fallback `"default"`)

- [ ] **Step 1: Write `msalConfig.ts`**

```ts
import { Configuration, PublicClientApplication, LogLevel } from "@azure/msal-browser";

export const msalConfig: Configuration = {
  auth: {
    clientId: import.meta.env.VITE_ENTRA_CLIENT_ID,
    authority: `https://login.microsoftonline.com/${import.meta.env.VITE_ENTRA_TENANT_ID}`,
    redirectUri: import.meta.env.VITE_ENTRA_REDIRECT_URI || window.location.origin,
  },
  cache: { cacheLocation: "localStorage" },
  system: { loggerOptions: { logLevel: LogLevel.Warning } },
};

export const loginRequest = {
  scopes: (import.meta.env.VITE_ENTRA_API_SCOPE as string | undefined)
    ? [import.meta.env.VITE_ENTRA_API_SCOPE]
    : ["openid", "profile"],
};

export const msalInstance = new PublicClientApplication(msalConfig);
```

- [ ] **Step 2: Implement `useSpecialist` + `AuthGate` + `LoginPage`**

`LoginPage`: industrial login with product name **Payroll Specialist**, short supporting line, single CTA “Sign in with Microsoft”.

`AuthGate`: use `AuthenticatedTemplate` / `UnauthenticatedTemplate` from `@azure/msal-react`.

`useSpecialist`: read `useMsal().accounts[0]`, derive id/name, `getAccessToken` via `acquireTokenSilent` then `acquireTokenPopup` fallback with `loginRequest.scopes`.

- [ ] **Step 3: Wire providers in `main.tsx`**

```tsx
import { MsalProvider } from "@azure/msal-react";
import { msalInstance } from "./auth/msalConfig";

await msalInstance.initialize();

createRoot(document.getElementById("root")!).render(
  <MsalProvider instance={msalInstance}>
    <App />
  </MsalProvider>,
);
```

- [ ] **Step 4: `.env.example`**

```env
VITE_ENTRA_CLIENT_ID=
VITE_ENTRA_TENANT_ID=
VITE_ENTRA_REDIRECT_URI=http://localhost:5173
VITE_ENTRA_API_SCOPE=
VITE_FOUNDRY_INVOKE_URL=
```

- [ ] **Step 5: Manual check**

Run: `cd web; npm run dev`  
Expected: Login page without env accounts; with valid Entra app + redirect URI, sign-in reaches shell placeholder.

---

### Task 6: App shell, routing, enter animation

**Files:**
- Create: `web/src/layouts/AppShell.tsx`, `web/src/layouts/AppShell.module.css`, `web/src/lib/animateEnter.ts`, `web/src/components/Toast.tsx`
- Modify: `web/src/App.tsx`

**Interfaces:**
- Consumes: `AuthGate`, `useSpecialist`
- Produces: routes `/`, `/queue`, `/drafts`, `/qa`, `/change-lists`, `/settings`; default redirect `/queue`
- Header: brand **Payroll Specialist**, specialist display name, **Run triage** button (handler wired in Task 11; for now call stub that no-ops or toast “Configure Foundry URL”)
- Nav labels exactly: Queue, Drafts, Q&A, Change lists, Settings

- [ ] **Step 1: `animateEnter.ts`**

```ts
import anime from "animejs";

export function animateEnter(root: HTMLElement | null) {
  if (!root) return;
  anime({
    targets: root.querySelectorAll("[data-enter]"),
    opacity: [0, 1],
    translateY: [8, 0],
    easing: "easeOutQuad",
    duration: 420,
    delay: anime.stagger(40),
  });
}
```

- [ ] **Step 2: Build `AppShell`**

Narrow left rail on `--rail`, active nav with amber left border, main content `--paper` or elevated ink panel per page. Use `NavLink` from react-router-dom.

- [ ] **Step 3: Wire `App.tsx`**

```tsx
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthGate } from "./auth/AuthGate";
import { AppShell } from "./layouts/AppShell";
import { QueuePage } from "./pages/QueuePage";
import { DraftsPage } from "./pages/DraftsPage";
import { QaPage } from "./pages/QaPage";
import { ChangeListsPage } from "./pages/ChangeListsPage";
import { SettingsPage } from "./pages/SettingsPage";

export default function App() {
  return (
    <BrowserRouter>
      <AuthGate>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to="/queue" replace />} />
            <Route path="queue" element={<QueuePage />} />
            <Route path="drafts" element={<DraftsPage />} />
            <Route path="qa" element={<QaPage />} />
            <Route path="change-lists" element={<ChangeListsPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </AuthGate>
    </BrowserRouter>
  );
}
```

Temporarily stub page components as `<EmptyState title="…" />` if pages not built yet — prefer creating minimal page files in this task that export empty shells so the app compiles.

- [ ] **Step 4: Manual check**

Expected: after auth, rail + five routes navigate; brand visible; staggered enter on shell children with `data-enter`.

---

### Task 7: Shared UI primitives

**Files:**
- Create: `web/src/components/EmptyState.tsx`, `web/src/components/EmptyState.module.css`, `web/src/components/PriorityBadge.tsx`, `web/src/components/CategoryChip.tsx`, `web/src/components/MasterDetail.tsx`, `web/src/components/MasterDetail.module.css`

**Interfaces:**
- Produces:
  - `EmptyState({ title, detail }: { title: string; detail: string })`
  - `PriorityBadge({ priority }: { priority: Priority })` — amber weight for 1–2
  - `CategoryChip({ category }: { category: Category })`
  - `MasterDetail({ list, detail, listLabel }: { list: ReactNode; detail: ReactNode; listLabel: string })` — asymmetric split (~38% / 62%)

- [ ] **Step 1: Implement components with CSS modules matching tokens**

Empty copy default: title `"Not connected yet"`, detail explains backend wiring pending.

- [ ] **Step 2: Smoke import from a page**

Ensure TypeScript build passes: `cd web; npm run build`.

---

### Task 8: Queue page (polished)

**Files:**
- Create: `web/src/pages/QueuePage.tsx`, `web/src/pages/QueuePage.module.css`

**Interfaces:**
- Consumes: `QueueItem`, `sortQueueItems`, `MasterDetail`, `EmptyState`, `PriorityBadge`, `CategoryChip`, `animateEnter`
- Produces: filters (category select + priority select), list + detail UI
- State: `items: QueueItem[]` starts `[]`; `selectedId`; filter values
- When `items.length === 0`: show empty state inside master–detail chrome (filters still visible)
- Detail actions (UI only, disabled or toast): “Open draft”, “Mark done”, priority adjust — do not invent rows

- [ ] **Step 1: Implement `QueuePage`**

Structure:

```tsx
// filters row
// MasterDetail
//   list: sorted+filtered map → button rows with PriorityBadge + CategoryChip + subject
//   detail: selected fields or “Select an item”
```

Use `useEffect` + `animateEnter` on mount.

- [ ] **Step 2: Manual check**

Expected: dense utilitarian queue layout; empty state message; filters interact; no fake emails; hover row highlight with amber accent line.

- [ ] **Step 3: Build**

Run: `cd web; npm run build`  
Expected: PASS.

---

### Task 9: Drafts page (structural)

**Files:**
- Create: `web/src/pages/DraftsPage.tsx`, `web/src/pages/DraftsPage.module.css`

**Interfaces:**
- Consumes: `DraftItem`, `MasterDetail`, `EmptyState`
- State: `drafts: DraftItem[] = []`, `selectedId`, `editBody`
- HITL buttons: Accept, Edit (toggle textarea), Discard, Send — disabled when no selection; on click without backend: toast “Not connected yet”

- [ ] **Step 1: Implement page with empty list + disabled HITL chrome**

- [ ] **Step 2: Build + navigate check**

---

### Task 10: Q&A page + Foundry wire

**Files:**
- Create: `web/src/pages/QaPage.tsx`, `web/src/pages/QaPage.module.css`

**Interfaces:**
- Consumes: `invokeFoundry`, `useSpecialist().getAccessToken`, `ChatMessage`
- Produces: working chat against Foundry when `VITE_FOUNDRY_INVOKE_URL` set
- On send: append user message → loading → `invokeFoundry(text, token)` → append assistant message with returned text
- On `FoundryError`: show inline error + Retry
- Sources panel: render only if assistant message has `sources` (leave empty for v1 parse; optional later JSON parse)

- [ ] **Step 1: Implement `QaPage`**

```tsx
async function onSend() {
  const token = await getAccessToken();
  const reply = await invokeFoundry(trimmed, token);
  // append assistant { content: reply }
}
```

- [ ] **Step 2: Manual check with local agent**

With Foundry/local invoke URL in `.env`: send “Why was my August paycheck lower?”  
Expected: HTTP round-trip; assistant bubble shows response text or clear error.

- [ ] **Step 3: Build**

Run: `cd web; npm run build`

---

### Task 11: Change lists + Settings + Run triage

**Files:**
- Create: `web/src/pages/ChangeListsPage.tsx`, `web/src/pages/ChangeListsPage.module.css`, `web/src/pages/SettingsPage.tsx`, `web/src/pages/SettingsPage.module.css`
- Modify: `web/src/layouts/AppShell.tsx` (Run triage handler)

**Interfaces:**
- Change lists: `ChangeListItem[] = []`, line checkboxes (local UI state only), Approve / Request clarification → toast not connected
- Settings: lookback days (number), mode `manual | recurring`, interval `2 | 4 | 24`, run history empty table, label controls “Local only until config API exists” for persist
- `runTriage`: `invokeFoundry(triageRunInput(specialistId), token)` from header + Settings button; toast success/error with status text

- [ ] **Step 1: Implement Change lists empty master–detail**

- [ ] **Step 2: Implement Settings form + Run triage shared handler**

Extract `web/src/api/triage.ts` if needed:

```ts
import { invokeFoundry, triageRunInput } from "./foundry";

export async function runTriage(specialistId: string, token?: string) {
  return invokeFoundry(triageRunInput(specialistId), token);
}
```

- [ ] **Step 3: Wire header button to `runTriage`**

- [ ] **Step 4: Manual check**

Run triage with URL configured → response toast; without URL → clear error.

- [ ] **Step 5: Full build + tests**

Run: `cd web; npm test; npm run build`  
Expected: all PASS.

---

### Task 12: Docs polish

**Files:**
- Modify: `web/README.md`, root `README.md` (short “Web UI” section pointing to `web/`)

**Interfaces:**
- Documents: install, `.env` vars, Entra redirect URI notes, `npm run dev`, how Q&A + TRIAGE_RUN map to agent

- [ ] **Step 1: Write `web/README.md`** with setup steps and wire-order note matching the spec

- [ ] **Step 2: Add 5–10 line section to root README**

- [ ] **Step 3: Final verification**

```powershell
cd web
npm test
npm run build
npm run dev
```

Expected: tests green; production build ok; all five nav areas reachable; Queue polished empty; Q&A/triage ready for env.

---

## Spec coverage checklist

| Spec item | Task |
|---|---|
| Vite + React + TS in `web/` | 1 |
| Industrial tokens / Frontend-Skill | 2 |
| Domain categories + queue sort | 3 |
| Foundry `{ input }` client | 4 |
| Entra MSAL | 5 |
| Shell + five routes | 6 |
| Shared empty/master-detail | 7 |
| Queue polish | 8 |
| Drafts HITL chrome | 9 |
| Q&A wire (final text) | 10 |
| Change lists + Settings + Run triage | 11 |
| Docs | 12 |
| No mock API | all |
| No FastAPI | all |
| Outlook add-in unchanged | all |

## Self-review notes

- Accent locked to amber (matches spec).
- `triageRunInput` / `invokeFoundry` signatures consistent across Tasks 4, 10, 11.
- Queue has no sample data (empty array only).
- Commit steps optional per user rule during execution.
