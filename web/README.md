# FEN web layer — zero-build static frontend

Plain HTML/JS/CSS, no build step. Talks to the FEN HTTP APIs (contract in
[`api.md`](api.md)).

## Contents

- `portal/` — classic DAO portal (`index.html`, `app.js`) and the Triadic view
  Scaffold → Consensus → Registry (`triadic.html`, `triadic.js`, vendored
  Cytoscape in `portal/vendor/`).
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

## Vercel deployment (static hosting)

`web/package.json` is a **detection marker only** (zero-build, no dependencies): it makes Vercel list `web/` in the Root Directory picker.

`vercel.json` in this directory wires everything:

- `framework: "other"` — zero-build static output;
- `ignoreCommand` — exit 0 when `web/` did not change since `HEAD^`, so
  backend-only pushes skip the deploy entirely;
- `rewrites` — `/` → classic portal, `/triadic` → triadic view, `/widget` →
  widget demo, `/embed` → dataset-owner embedding example.

One-time project setup (Vercel dashboard, import
`riznykst/fen-triadic-synthesis`):

1. Framework Preset: **Other** · Root Directory: **`web`** ·
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
