# FEN web layer — zero-build static frontend

Plain HTML/JS/CSS, no build step. Talks to the FEN HTTP APIs (contract in
[`api.md`](api.md)).

## Contents

- `portal/` — classic DAO portal (`index.html`, `app.js`) and the Triadic view
  Scaffold → Consensus → Registry (`triadic.html`, `triadic.js`, vendored
  Cytoscape in `portal/vendor/`).
- `shared/` — the single implementations shared by the portal views
  (TECH-DEBT P2 consolidation):
  - `live.js` (`fenLive`): SSE live-updates helper (EventSource + 15s
    polling fallback + catch-up on reopen);
  - `escape.js` (`fenEscapeHtml`/`fenJsAttr`/`fenSafeHref`): one escaping
    implementation;
  - `api-base.js` (`fenApiBase`): the query → localStorage → default base-URL
    convention;
  - `theme.js` (`fenTheme`): the light palette + status→color map for
    JS-rendered UI (keep in sync with the portal CSS variables).
  All four are UMD (window + module.exports) so `node --test web/tests/`
  can exercise them (see `web/tests/`). The Flow-2 widget mirrors the
  semantics but stays self-contained for third-party embedding.
- `tests/` — Node tests for `web/shared/*` (`node --test "web/tests/*.test.js"`;
  wired into the CI `test` job).
- `widget/` — embeddable `<fen-status>` widget (Flow 2) + `demo.html` +
  `embed-example.html` (dataset-owner embedding example).

## Local run

`docker compose up` from the repo root: the status-api serves this directory
at **http://localhost:8082/web/portal/index.html** (`FEN_WEB_DIR=web`).
Default API endpoints are `http://localhost:8100` (mock FEN) and
`http://localhost:8082` (status API); override them per page:

- Triadic view: query params `?fen_mock_base=...&fen_status_base=...`
  (persisted to `localStorage`), or set the keys directly:
  `localStorage.setItem("fen_mock_base", "...")`.
- Classic portal: query params `?fen_mock_base=...&fen_status_base=...`
  (persisted to `localStorage`), or type the base URL into the fields on
  the page.
- Widget demo: query param `?fen_status_base=...`; the widget itself takes
  an `api-base` attribute, e.g.
  `<fen-status annotation-id="a1" api-base="https://...">`.

## CI scope

Frontend-only pushes (touching only `web/`) run the 111 unit tests via
`.github/workflows/web.yml` and never touch Docker: `ci.yml` ignores
web-only pushes (`paths-ignore: ['web/**']`), because the CI stack cannot
share the published host ports with a locally running dev stack and a
web-only change does not need the e2e pipeline. Mixed pushes run both
workflows (unit suite twice — harmless).

## Vercel deployment (static hosting)

Zero-build static layer, deployed from the **repository root**: `vercel.json`
at the repo root is the single source of truth (there is intentionally no
`web/vercel.json`), so `vercel` can be run from the repository root.

- zero-build static: no `framework` preset in the config (the current Vercel
  schema has no "other" value — plain static is the default when `framework`
  is omitted; "Other" is chosen in the dashboard);
- `cleanUrls: true` — extension-less pretty URLs;
- `ignoreCommand` — `git diff --quiet HEAD^ HEAD -- web/` exits with 0 when
  the `web/` layer did not change since `HEAD^`, so backend/docs-only pushes
  skip the deploy entirely;
- `rewrites` — `/` → landing (`web/index.html`), `/portal` → classic DAO
  portal, `/triadic` → triadic view, `/widget` → widget demo, `/embed` →
  dataset-owner embedding example (all pages live under `web/`).

One-time project setup (Vercel dashboard, import
`riznykst/fen-triadic-synthesis`):

1. Framework Preset: **Other** · Root Directory: **repository root** ·
   Build/Install commands: empty.
2. Deploy. Every push to `main` touching `web/` auto-deploys.

Production notes:

- Backends must be reachable over **HTTPS** — the browser blocks
  `EventSource`/`fetch` to plain HTTP from an HTTPS page (mixed content).
- Both FastAPI services already send CORS headers
  (`FEN_CORS_ORIGINS`, default `*`); narrow it to your Vercel origin when
  going live.
- SSE (`/events`) is consumed directly from the backend, not proxied through
  Vercel.
