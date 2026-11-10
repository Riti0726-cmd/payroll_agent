# Payroll Specialist — Outlook add-in

A task pane that shows the Payroll Specialist agent's work next to the email being read in Outlook.

The project was scaffolded with Microsoft's Yeoman generator (`yo office`, React + TypeScript, unified manifest). The UI follows the **web app's design system** (`web/src/styles` tokens, Syne + IBM Plex Sans, ink/paper panels with one amber accent, and the same badges, empty states, line cards and Q&A console). It has a light/dark toggle and starts in Outlook's theme.

| Tab | What it does |
|---|---|
| **This email** | Category and priority for the open email, plus any extracted fields such as client and employee. You can change the priority (P1–P5) or mark the email done. **Draft reply**: edit the draft, then Accept or Discard it. **Insert into reply** opens an Outlook reply with the draft filled in. Nothing is sent until you press Send. **Change list**: review the lines, then Approve or mark *Needs clarification*. |
| **Ask** | Payroll Q&A chat (`/qa/stream`). The *Include this email* toggle sends the open email's text along with your question. |
| **Queue** | **Run triage** with live progress (`/triage/stream`), and the open queue sorted by priority. Click an item to open that email. |

The pane can be pinned. When it is pinned, it updates as you select a different email.

## Project layout

```
manifest.json          Unified manifest (mailRead ribbon button, pinnable task pane, Mailbox 1.5)
webpack.config.js      Yeoman template build + .env inlining + /api dev proxy
eslint.config.mjs      Lint config (used by office-addin-lint)
assets/                Icons (currently the template's placeholders; see "Before rollout")
src/
  config.ts            Build-time settings (from .env)
  api/                 Backend clients: http.ts, workbench.ts (lookup/queue/drafts/changelists),
                       streams.ts (QA + triage SSE), sse.ts
  auth/                naa.ts (NAA + dialog fallback), dialog.html/.ts, useSpecialist.tsx
  office/mailbox.ts    Office.js wrappers (current item, body, reply form, open message, ItemChanged)
  lib/                 markdown.ts (draft → reply HTML), queueSort.ts
  styles/              tokens.css + grain.css (copied from web/src/styles) and global.css
  theme/               Light/dark provider (port of web ThemeProvider)
  taskpane/            index.tsx, taskpane.html, components/ (ui/ = ports of web/src/components), hooks/, triage/
  types/domain.ts      Shared shapes (mirrors web/src/types/domain.ts)
  test/setup.ts        Office.js mock for Vitest
```

The request and response shapes match `web/src/api/*`, and the styles match `web/src/styles` and `web/src/components`. The web app is the source of truth for both. If you change an endpoint or a design token, update both.

## Backend requirements

These are in `src/payroll_specialist/`:

- **`GET /emails/lookup?specialist_id=&rest_id=&internet_message_id=`** (`emails_http.py`) returns one email's triage record. It looks up the Graph REST id first, then falls back to `internet_message_id`, because REST ids change when an email is moved to another folder. Results are limited to the specialist's mailbox.
- **Migration:** run `sql/003_add_internet_message_id.sql` once against Neon:
  ```
  psql "$DATABASE_URL" -f sql/003_add_internet_message_id.sql
  ```
  Emails triaged before the migration only get an `internet_message_id` when triage sees them again. Until then they can only be found by REST id.
- **CORS:** set `CORS_ALLOWED_ORIGINS` to the add-in's origin(s) when the add-in calls a deployed backend directly. You don't need it for local development, because the webpack dev server proxies `/api`.

## Local development

1. Start the backend: `.\.venv\Scripts\python.exe src\payroll_specialist\main.py` (port 8088).
2. In `outlook_addin/`:
   ```
   copy .env.example .env      # fill in VITE_ENTRA_* (or VITE_AUTH_DISABLED=true for UI-only work)
   npm install
   npm start                   # installs dev certs (first run asks to trust a localhost CA), serves https://localhost:3000, sideloads into Outlook
   npm stop                    # unloads the sideloaded add-in
   ```
   If sideloading doesn't work in new Outlook or Outlook on the web, run `npm run build`. Then, in Outlook on the web, go to **Get Add-ins → My add-ins → Add a custom add-in → Add from file** and choose `dist/payroll-specialist-addin.zip`.
3. Checks:
   ```
   npm test        # Vitest
   npm run lint    # office-addin-lint (ESLint + Prettier)
   npm run typecheck
   npm run validate  # unified manifest schema
   ```

## Sign-in (Entra)

The add-in reuses the **same SPA app registration as `web/`**, with the same `VITE_ENTRA_CLIENT_ID`, `VITE_ENTRA_TENANT_ID` and `VITE_ENTRA_API_SCOPE`. It requests the API scope plus Graph `Mail.Read`. Triage needs `Mail.Read`, the same as in the web app.

On the app registration, under **Authentication → Single-page application**, add these redirect URIs:

- `brk-multihub://localhost:3000`, for Nested App Authentication. Outlook signs the user in silently with the account already signed in to Outlook.
- `https://localhost:3000/dialog.html`, the fallback for Outlook clients without NAA support. This opens a sign-in dialog.

When the add-in is deployed, add the same two URIs for the production host as well.

## Deploying

1. Host the static files in `dist/` on HTTPS, for example on Azure Static Web Apps. This isn't provisioned yet.
2. In `.env`:
   - Set `ADDIN_PROD_URL=https://<host>/`. The build rewrites `https://localhost:3000/` in the manifest to this value.
   - Set `VITE_API_BASE_URL` to the backend's HTTPS URL.
3. Also replace `localhost:3000` in `validDomains` in `manifest.json` with the production host. The build doesn't change this entry.
4. On the backend, add the add-in origin to `CORS_ALLOWED_ORIGINS`.
5. Run `npm run build`. It produces `dist/payroll-specialist-addin.zip`. Upload it in the **Microsoft 365 admin center → Settings → Integrated apps → Upload custom apps**.

## Before rollout

- **Icons:** `assets/` still has the Yeoman template icons. Replace them with Engage PEO artwork at the same sizes: `color.png` 192×192, `outline.png` 32×32 transparent, and `icon-16/32/64/80/128.png`. Keep the logo unaltered, with proper clear space.
- **Developer URLs:** `privacyUrl` and `termsOfUseUrl` in `manifest.json` point at assumed engagepeo.com paths. Check that they exist.
- **API auth:** the backend doesn't validate the bearer token on `/queue`, `/drafts`, `/changelists` or `/emails/lookup`, and `specialist_id` comes from the client. Before exposing the backend beyond the internal network, add Entra JWT validation and take `specialist_id` from the token claims.
