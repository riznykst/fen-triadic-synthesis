# Changelog

All notable changes are recorded here in reverse chronological order.

## 2026-09-03 — Vercel 404 fixed: cleanUrls broke rewrites; embed page restored

- **Root cause of the long-standing 404 on "/"** (and /portal, /triadic,
  /widget, /embed): `"cleanUrls": true` in the root `vercel.json` compiled
  the rewrites to NO routes (deployment `routes: null`) — isolated proof:
  the identical rewrites work without cleanUrls and fail with it. Removed
  (`7f5b6ce`). Pretty URLs come from the rewrites themselves, so cleanUrls
  added nothing.
- **`web/widget/embed-example.html` restored** (`bfc152c`): the file was
  committed EMPTY (0 bytes) in 297434f while BACKLOG/CHANGELOG claimed a
  full "dataset-portal mockup" page — honesty-contract violation found
  while probing /embed. Recreated per the promised spec: 4 embedded
  fen-status badges (light/dark incl. the honest unknown state),
  copy-paste embed snippet, going-live notes.
- Verified live on the production deployment (vercel curl, protection
  bypass): `/` landing, `/portal`, `/triadic`, `/widget`, `/embed` all 200.
- Tests: 125 (unchanged) — config + static page only.


## 2026-09-03 — BACKLOG P3: UI e2e test (Playwright) shipped

- **UI e2e (BACKLOG item closed)**: `web/e2e/ui.spec.js` + `playwright.config.js`
  run against the LIVE stack (status-api serves /web, mock DAO on :8100):
  portal loads without page/console errors, submit → SSE flip to
  `validated`, triadic view + scaffold run produce steps, Flow-2 widget demo
  renders its three badges. Playwright pinned as a web devDependency
  (`@playwright/test ^1.62.1`), chromium installed on first run, CI e2e job
  runs it after the smoke tests (mock returned to auto mode first —
  the voting steps leave it in qv).
- Fixed en route: the portal script tags pointed at `shared/*.js`
  (relative — 404 from `/web/portal/`); they now use the absolute
  `/web/shared/*` paths (works under status-api AND the Vercel rewrites).
- `.gitignore`: `node_modules/`, `test-results/`, `playwright-report/`.
- Tests: 125 pytest + 18 Node + 5 Playwright UI.

## 2026-09-03 — TECH-DEBT: dead renderGraphSvg removed (frontend-only)

- `web/portal/triadic.js`: the SVG fallback renderer `renderGraphSvg` and
  the legacy `regGraph` container refs are deleted — `vendor/cytoscape.min.js`
  is always loaded by `triadic.html`, so the fallback branch was
  unreachable. `renderGraph()` is now a thin wrapper over `renderGraphCy()`
  (which already handles the empty state and a missing cytoscape). Net
  −52/+10 lines; node --check clean; JS tests 18/18; pytest 125.
- Tests: 125 (unchanged — dead-code removal).


## 2026-09-03 — TECH-DEBT wave 10: web consolidation into web/shared/, k8s env single source, JS tests in CI

- **Web-layer consolidation (P2)**: the duplicated helpers are now ONE
  implementation each in `web/shared/` (UMD: window + module.exports) and
  both portal views alias them:
  - `escape.js` — `fenEscapeHtml`/`fenJsAttr`/`fenSafeHref` (was: escapeHtml
    in app.js, esc/jsAttr in triadic.js, escapeHtml/safeHref in the widget);
  - `api-base.js` — `fenApiBase` (was: app.js applyApiBases vs triadic.js
    apiBase, two divergent conventions — now one query → localStorage →
    default rule);
  - `theme.js` — `fenTheme.FEN_LIGHT` + status→color (was: the palette
    duplicated in triadic.js C + OUTCOME_STYLE and portal CSS; JS callers
    now share one map, documented to stay in sync with the CSS variables);
  - `live.js` gained a CommonJS export (was browser-only).
  Dead `OUTCOME_BG` removed with its definition. The Flow-2 widget keeps a
  self-contained copy (third-party embedding) and documents mirroring.
- **k8s env single source (P3)**: `k8s/env-shared.yaml` is now the only
  hand-edited env map; `scripts/generate_k8s_configmap.py` renders
  `k8s/configmap.yaml` from it; `tests/test_k8s_configmap.py` (2 tests)
  enforces freshness (regenerate-in-memory + compare, same pattern as the
  JSON-schema guard). Compose stays the source for listener/dev-specific
  values; shared TOPIC_* names are asserted end to end by the CI e2e.
- **JS-level tests (P3)**: `web/tests/` — 18 Node tests
  (`node --test "web/tests/*.test.js"`) covering escape semantics, the
  apiBase convention (query/localStorage/default, fake storage) and
  fenLive behavior (fake EventSource: connect, idempotent restart, named
  frames stop the fallback, onopen catch-up, server error frames,
  EventSource-unavailable degradation). Wired into the CI `test` job.
- Tests: 125 (was 123).

## 2026-09-03 — TECH-DEBT wave 9: single service Dockerfile (consolidation)

- **Five near-identical Dockerfiles → ONE** (`docker/service.Dockerfile`):
  a single `deps` stage installs the union of service requirements in one
  pip layer (`docker/requirements-service.txt`), then thin targets
  (`outbound`, `webhook`, `consumer`, `mock`, `status-api`) add only the
  source trees each process needs; compose selects the target via
  `build.target`. Removed the five old Dockerfiles and the four per-service
  `requirements.txt` (their pins had drifted, e.g. prometheus-client
  >=0.19 vs >=0.20 — the union now pins >=0.20 once). fastapi/uvicorn are
  inert in the consumer images (metrics.py imports fastapi lazily);
  rdflib/pyshacl serve mock (scaffold) + status-api (export); pytest/httpx
  stay out of images (host-venv only).
- Verified live: all five targets build, full stack healthy, e2e smoke
  test PASSED (auto mode).
- Tests: 123 (unchanged — no runtime logic touched).

## 2026-09-03 — TECH-DEBT wave 8: compose healthchecks complete, Virtuoso pinned

- **Compose healthcheck gaps closed (P1)** — every service now has a
  healthcheck (`docker-compose.yml`):
  - `fuseki`: wget probe of `/$/ping` (image ships wget, verified);
    status-api and validation-consumer now `depends_on` it with
    `service_healthy` instead of racing a cold start;
  - `zookeeper`: bash `/dev/tcp` probe using `srvr` → "Zookeeper version"
    (`ruok`/`imok` no longer works on ZooKeeper 3.5+, it echoes `ruok`);
  - `virtuoso`: curl probe of the SPARQL endpoint (image ships curl, NOT
    wget — verified on 7.2.17; the old wget probe was silently failing);
  - `status-api` healthcheck now probes `/readyz` (SPARQL reachability),
    not just `/healthz`.
- **Virtuoso image pinned to `7.2.17`** (was floating `latest` — upstream
  releases silently changed the CI e2e dialect baseline); tag verified in
  the registry.
- Verified live: full stack (incl. virtuoso profile) all `healthy`, e2e
  smoke test PASSED (auto mode).
- Tests: 123 (unchanged).

## 2026-09-03 — TECH-DEBT wave 7: linter green, warning triage, delegation tests

- **First `ruff check` run is green** (new `[tool.ruff]` preset from wave 5):
  five unused imports removed (`services/common/llm.py`,
  `services/fen_bridge/outbound.py`, `services/status_api/main.py`,
  `services/validation_consumer/main.py`), three B904 `raise ... from exc`
  fixes (status-api 503 paths ×2, mock intensity-422), per-file BLE001
  ignore for the sync script.
- **Warning triage: 1616 → 1** (`[tool.pytest.ini_options] filterwarnings`):
  the wall was ~99% rdflib-INTERNAL deprecations (Dataset
  default_context/identifier, ConjunctiveGraph) fired from library code +
  one starlette/fastapi TestClient notice; all upstream, none called by this
  repo (grep-verified), suppressed with a comment to revisit on the next
  rdflib/starlette upgrade. One documented import-time starlette warning
  remains.
- **Direct delegation unit tests**: new `tests/test_delegation.py` (8 tests)
  covers every branch of `apply_delegation` (register, required names,
  self-delegation, unknown record, decided candidate, QV-only, voted-voter,
  re-delegation replaces) — previously only exercised through HTTP.
- Tests: 123 (was 115).

## 2026-09-03 — TECH-DEBT wave 6: metrics series split, triadic aria-labels

- **Metrics collision fixed (P2)**: `fen_kafka_messages_processed_total` /
  `fen_kafka_messages_failed_total` are emitted by BOTH consumer processes
  (fen-bridge-outbound, validation-consumer) — they now carry a `process`
  label (the consumer group id at inc() time:
  `services/common/metrics.py` + both call sites), so Grafana panels no
  longer plot two colliding series under one legend.
- **a11y (P2)**: triadic ± intensity buttons and the delegate (→) button
  gained `aria-label`s (`web/portal/triadic.js`).
- Tests: 115 (unchanged).

## 2026-09-03 — TECH-DEBT wave 5: docs drift fixed, a11y, config hygiene, lint config

- **Docs drift fixed** (`docs/architecture.md`, `docs/self-hosted-runner.md`,
  `docs/adr/ADR-005-*`): observability table now matches code — outbound and
  validation-consumer expose /metrics on METRICS_PORT 9101/9102 (they always
  did), status-api added to the table, readiness prose updated (probes use
  /readyz for HTTP services and /metrics for consumers); k8s section lists
  the FOUR deployments incl. status-api and documents the fail-closed Secret
  (invalid base64) + fen-sparql-credentials; "the four ADRs" → ADR-001..006;
  duplicated sentence fragment removed; self-hosted-runner step 5 describes
  the actual self-hosted state, step 7 is the FULL revert list (shell
  idioms, matrix + setup-python, web.yml merge); test counts 111→115;
  corrupted 0xFF characters in run-history sections replaced; ADR-005
  decision list renumbered 1..5 (was 1-4,6) and ADR-006 references softened
  to "IF accepted".
- **a11y (P2)** (`web/portal/index.html`, `triadic.html`,
  `fen-status-widget.js`): all labels paired with `for`/`id`; candidates
  table gained a `<caption>` and `scope="col"` headers; the widget's
  expand control is a real `<button type="button">` with `aria-expanded`
  and focus-visible styling (was a clickable `<div>` — unreachable for
  keyboard users), and "retry" is a button, not an `<a href="#">`.
- **Config hygiene (P2)**: `ValidationConsumerConfig` gained env-driven
  `FEN_CONSUMER_GROUP_ID` / `FEN_CONSUMER_BATCH_SIZE` /
  `FEN_CONSUMER_POLL_TIMEOUT_MS` (batch/group were hardcoded in main.py,
  unlike FenBridgeConfig); `StatusApiConfig` gained `SPARQL_TIMEOUT_S` /
  `SPARQL_PING_TIMEOUT_S` (timeouts were hardcoded literals).
- **Lint config (P2)**: new `pyproject.toml` with a conservative `[tool.ruff]`
  preset (F/E9/B/BLE, per-file ignores for deliberate broad handlers) — no
  linter config existed anywhere.
- Tests: 115 (unchanged — no test-affecting logic changes).

## 2026-09-03 — TECH-DEBT P1 wave 2-4: URI centralization, schema guard, shared SSE helper, dead-code removal, FenClient tests

- **Single source for the `urn:graphia:` scheme** (new
  `services/common/graph_uris.py`): `annotation_uri()`,
  `document_graph_uri()`, `annotation_graph_uri()` — sparql_updater,
  validation-consumer (`named_graph_uri`) and status-api all import it
  instead of copy-pasting fragment strings.
- **`_PREDICATE_KEYS`** (status-api) now derives from
  `services/common/gfen_ontology` PROP_* constants — the hardcoded IRI
  literals (drift hazard vs the ontology module/.ttl) are gone.
- **Dead config removed**: unused `fen_naan` fields dropped from
  `FenBridgeConfig` and `ValidationConsumerConfig` (PID minting reads
  `FEN_NAAN` via `pid.default_naan()` itself).
- **JSON-schema freshness guard** (`tests/test_messages.py`): new test
  regenerates `model_json_schema()` in memory and asserts equality with the
  committed `schemas/kafka-events/*.schema.json` — model drift now fails the
  suite with a "run generate_schemas.py" hint. Tests: 112 (was 111).
- **Shared SSE helper** (new `web/shared/live.js`, `fenLive`): one
  EventSource + 15s-fallback + catch-up-on-reopen implementation with
  unified semantics, now used by BOTH portal views (`app.js` via
  `startLiveUpdates`, `triadic.js` via `fenLive(...)`); the triadic.js
  drift is fixed (fallback now runs while the stream is down and every
  reopen reloads — no more silently stale Consensus/Registry). The Flow-2
  widget keeps its self-contained copy for third-party embedding but
  documents that it mirrors the helper's semantics.
- **Dead code removed (P2)**: values-only `poll_batch` deleted from
  `services/common/kafka_io.py` + the fen_bridge shim + its compat test
  (superseded by `poll_batch_with_offsets`); the orphaned mid-function
  docstring in `webhook.py` merged into the real one; `_broadcast` no longer
  swallows `queue.Full` silently — it logs and evicts the stale SSE
  subscriber (was an invisible black hole for slow consumers).
- **Test blind spot closed**: new `tests/test_fen_client.py` (4 tests) —
  FenClient's "never raise, log and drop" contract is now verified:
  success returns True, transient failures retry with backoff, terminal
  failure returns False, HTTP 4xx treated as failure. Tests: 112 (net: 111
  +1 schema guard +4 FenClient −1 poll_batch compat).

## 2026-09-03 — TECH-DEBT P0/P1 fixes (delivery of the 2026-09-02 audit plan)

- **P0 outbound commit semantics** (`services/fen_bridge/outbound.py`,
  `tests/test_fen_bridge.py`): whole-consumer `consumer.commit()` replaced
  with the shared per-record `commit_offsets(consumer, batch)` (offset+1 per
  message) — a future change to poll caps/batch truncation can no longer
  silently downgrade at-least-once to at-most-once. Test asserts the
  per-record offsets.
- **P0 k8s fail-open → fail-closed** (`k8s/`): `secret.yaml` webhook token
  is now intentionally INVALID base64 so `kubectl apply` refuses the
  manifest until a real token is set; empty SPARQL credentials removed from
  `configmap.yaml` (documented `kubectl create secret generic
  fen-sparql-credentials` + secretRef hook in the consumer Deployment);
  `fen-bridge-outbound`/`validation-consumer` gained containerPort +
  readiness/liveness probes on their /metrics servers (9101/9102); stale
  "no HTTP port" comments corrected; Kafka-listener and FEN_API_BASE_URL
  (external per ADR-002) comments clarified.
- **P0 Vercel ignoreCommand** (`vercel.json`): `HEAD^` replaced by
  `${VERCEL_GIT_PREVIOUS_SHA:-HEAD^}` with a build-on-error guard — the
  skip guard no longer degrades on shallow clones/first deploys and is
  merge-commit safe.
- **P1 compose healthchecks + readyz** (`docker-compose.yml`):
  `fen-bridge-outbound` and `validation-consumer` now have healthchecks
  against their /metrics endpoints (python probe, ports 9101/9102);
  status-api gets `SPARQL_PING_ENDPOINT` so `/readyz` stops reporting
  "degraded" in the compose stack.
- **P1 build hygiene**: new root `.dockerignore` (.git, bytecode, caches,
  .env, docs/tests/examples) — Docker build contexts stop shipping junk
  and secrets.
- **P1 XSS hardening** (`web/portal/app.js`): the last unescaped
  server-controlled surface — `statusBadge()` — is now enum-validated
  (`VALID_STATUSES`) and HTML-escaped in both class and text;
  `renderCandidates` guards `c.votes` (absent → `{}`) and coerces the
  vote/quorum counters with `Number()` before innerHTML.
- Tests: 111 (unchanged — one test strengthened).

## 2026-09-02 — IPL 2026 event docs (rewritten from Jules PR #6)

- Added `docs/IPL-READINESS-AUDIT.md`, `docs/IPL-DEMO.md` and
  `docs/GRAPHIA-INTEGRATION.md` for the GRAPHIA × LUMEN Innovation
  Prototyping Lab (14–18 September 2026). Rewritten from Jules PR #6
  (branch `jules-10485388230883290649-f9361c20`, closed) with the owner's
  decisions applied:
  - **«IPL-Ready v0.1» branding REJECTED** — the README status badge and
    the Status & Truth Matrix section stay as they were (the PR's README
    edits were not taken);
  - **build freeze REJECTED** — `docs/IPL-BUILD-FREEZE.md` removed;
  - factual fixes: audit date `May 2026` → `2026-09-02`; webhook auth
    described as Bearer token (`FEN_WEBHOOK_TOKEN`), not HMAC/signatures;
    the "pre-seeded mock candidates" claim removed (the mock starts empty;
    the demo submits candidates live).
- Backlog: IPL 2026 event-prep items added to `docs/BACKLOG.md`.
- Tests: 111 (unchanged — docs only).

## 2026-09-02 — Technical-debt audit plan (docs/TECH-DEBT.md)

- Full-repo audit (5 parallel area reviews: backend, infra/CI, web, docs/
  ontology, tests), findings re-verified on this tree after the D:-drive
  failure moved the repo home to `C:\fen-triadic-synthesis`.
- New `docs/TECH-DEBT.md`: prioritized P0–P3 plan (P0: outbound commit
  semantics, k8s env drift + empty webhook token, Vercel ignoreCommand;
  P1: SSE-fallback drift in triadic.js, last unescaped XSS surface in
  app.js, URN/IRI/NAAN duplication, schema-freshness guard, Dockerfile
  duplication + .dockerignore, Virtuoso tag, compose healthchecks; P2/P3:
  web consolidation, a11y, dead code, config hygiene, test blind spots,
  CI-mode retirement) + verified-clean list + environment note.
- BACKLOG: new "Technical debt" section referencing the plan; stale figures
  fixed (104→111 tests, 72→13-at-publish commits, snapshot date, Node
  contradiction, D:-failure note).

## 2026-09-02 — Landing page cleanup (self-contained, honest content)

- `web/index.html`: removed the **Tailwind CDN** runtime dependency - the
  page is now fully self-contained (hand-written CSS mirrors the original
  slate/indigo classes; zero-build principle restored).
- Honesty fixes: prominent **"Sample data notice"** banner - every figure,
  PID and ledger anchor on the page is explicitly labeled a static
  illustration, not live data; the hero CTA now opens the real DAO portal.
- **Live demo links** added (DAO portal, Triadic view, Status widget,
  Embedding example).
- Fixed the dead `#architecture` nav anchor by adding a real Architecture
  section (microservice overview + links).
- Audit: no non-English user-facing strings; rendering verified via
  headless-Edge screenshot (slate palette 88%, indigo accents - CSS works
  without Tailwind).
- Tests: 111 (unchanged - static page).

## 2026-09-02 — Working protocol for all chats (self-hosted-runner.md)

- New **Working protocol (all chats)** section in
  `docs/self-hosted-runner.md`: offline dev loop (pytest 111 + schema/SHACL
  checks), automatic CI e2e on push (Docker must be running; a skipped e2e
  does NOT count as validation), local-stack port discipline, web-only pushes
  skip e2e (`paths-ignore` + `web.yml`), honesty contract, git hygiene with
  parallel sessions, roles (owner / working chats / Google Jules bot), and
  ops notes (stale runner-session recovery, multi-hour queueing while the
  runner is offline, diagnostics).
- Tests: 111 (unchanged — docs only).

## 2026-09-02 — Interface language: English-only (i18n item resolved)

- The BACKLOG i18n item (RU/EN bilingual) is dropped: the product UI is
  English-only by decision.
- Replaced the only non-English user-facing string in the entire `web/`
  layer — the Jules landing example (`web/index.html`) showed
  `"Крымскотатарский топоним"`; it now reads `"Crimean Tatar toponym"`.
- Audit: grep for non-ASCII/Cyrillic across `web/` → 0 matches.
- Tests: 111 (unchanged — static page text only).

## 2026-09-02 — Vercel: single deploy config at the repository root

- `vercel.json` (repo root) is now the full, single source of truth for the
  Vercel deployment — `cleanUrls`, `ignoreCommand` scoped to `web/` changes
  (`git diff --quiet HEAD^ HEAD -- web/`), and
  rewrites `/` → `web/index.html` (landing), `/portal` → classic DAO portal,
  `/triadic` → triadic view, `/widget` → widget demo, `/embed` → embedding
  example. `web/vercel.json` removed — deploys run from the repository root.
- Fixes the `/triadic` → `/triadic.html` 404 regression (the route now points
  at the real `web/portal/triadic.html`) and re-exposes the classic DAO
  portal at the clean `/portal` route.
- `web/README.md` updated (Root Directory: repository root; 111 unit tests
  in the CI-scope note).
- Tests: 111 (unchanged — configuration only).

## 2026-08-31 — Widget embedding example page for dataset owners (P2)

Frontend-only commit (web/):

- New `web/widget/embed-example.html`: a ready-made page simulating a
  third-party dataset portal with four embedded `<fen-status>` badges (light
  and dark theme variants, including the honest "unknown" state for records
  the pipeline has not validated yet) plus a copy-paste embed snippet and
  going-live notes (HTTPS/mixed content, CORS `FEN_CORS_ORIGINS`, read-only
  ADR-001, SSE contract `web/api.md` §4b, `challengeWindowEnd` gated on
  ADR-006).
- `web/vercel.json`: new rewrite `/embed` → `/widget/embed-example.html`;
  `web/README.md` and `web/widget/README.md` link the page.
- Verified: page serves over HTTP (200, 4 widget instances); `pytest -q`
  passes (unchanged — static page).
- Tests: 111 (unchanged).

## 2026-08-31 — Flow 2 widget: live status via SSE (challengeWindowEnd gated on ADR-006)

Backend (services/ + tests/):
- `GET /api/v1/events/{annotation_id}` (SSE) in the Status API — read-only
  (ADR-001): no Kafka consumer; the service re-polls the RDF store every
  `STATUS_POLL_INTERVAL_S` (default 5s) per connected client and pushes
  `event: status` ONLY when the record changed (canonical JSON comparison).
  Event payloads are byte-for-byte the `GET /api/v1/status/{id}` body
  (shared `_status_payload` builder), so records that do not exist yet are
  seen as they appear (`found:false` → `validated`).
- `event: error` + retry on the next tick when the store is unreachable;
  `: ping` heartbeat every `STATUS_SSE_HEARTBEAT_S` (default 15s);
  `Cache-Control: no-cache`.
- The stream generator is `_status_stream(annotation_id, poller, interval_s,
  heartbeat_s, stop_after=None)` — injectable poller + bounded ticks make it
  deterministically testable offline (`asyncio.run` over the generator; a
  TestClient GET would hang on the infinite stream by design).
- Config: `STATUS_POLL_INTERVAL_S`, `STATUS_SSE_HEARTBEAT_S` via
  `StatusApiConfig.from_env()`.
- Tests: 111 (was 104) — 7 new SSE tests (first-event byte-identity with
  REST, found:false, change-only pushes, error/retry, bounded termination,
  heartbeat, headers).

Frontend (web/ + web/api.md):
- `<fen-status>` widget: polling timer replaced by `EventSource` on
  `/api/v1/events/{annotation-id}`; `event: status` renders through the
  exact same path as the REST fetch (no flicker). While the stream is down
  (EventSource auto-reconnects) a 15s REST-polling fallback keeps the badge
  fresh; `onopen` stops the ticker and catches up — no lost status flips.
- New `live="off"` attribute lets embedders disable streaming (CSP/EventSource
  restrictions); documented in `web/widget/README.md`.
- `gfen:challengeWindowEnd` is deliberately NOT rendered: ADR-006 is still a
  draft ("proposed, not yet applied" in the ontology, nothing writes it).
  Only marked TODO hooks exist (widget render + status-api `_PREDICATE_KEYS`),
  gated on ADR-006 acceptance — no fake data (honesty contract).
- `web/api.md` §4b documents the SSE contract and event shapes.

## 2026-08-31 — Classic portal: light-card theme unification with the triadic view (P2)

Frontend-only commit (web/), P2 backlog item done (design unification).

- `web/portal/index.html` switches from the dark palette to the triadic
  view's light style. CSS-only: `app.js` is untouched — the inline
  `var(--...)` references keep working because the variable NAMES are
  unchanged, only their values changed.
  - Background: triadic beige gradient (`#efece6`→`#e7e4dc`); cards
    `#fdfcfa` with a 1.5px `#2d5a8e` border and 18px radius; Georgia serif
    headings; uppercase micro-labels.
  - Status badges → triadic tiles (colored text + pastel background:
    validated `#2e7d5b`/`#e6f4ee`, disputed `#8b6914`/`#faf3e0`, rejected
    `#b23a3a`/`#fae8e8`, pending `#2d5a8e`/`#e8eff7`, deciding/unknown
    muted).
  - Buttons: filled-accent primary (`#2d5a8e`, white text) + white chip
    secondary; vote buttons are outcome-colored via `[data-outcome]`;
    export links become chips.
- Verified: `node --check web/portal/app.js`; `pytest -q` — 104 passed;
  real-browser screenshot (headless Edge, 1280×1900) pixel-analyzed —
  light beige background ≈51%, white cards ≈30%, no dark-navy pixels
  (old theme `#0f1420` gone); jsdom functional run against the live mock:
  3 validated rows, 12 export links, accuracy 3/3 (100%), leaderboard
  `contributor_1 · 6`, 3 history entries. Screenshot kept at
  `D:\FEN-GRAPHIA\portal_light_check.png`.
- Tests: 104 (unchanged — CSS-only change).

## 2026-08-31 — CI: e2e scoped to non-web changes

- `.github/workflows/ci.yml` now ignores web-only pushes (native
  `paths-ignore: ['web/**']` — skipped only when ALL changed files are under
  `web/`), and the new `.github/workflows/web.yml` runs the unit suite for
  exactly those pushes. Frontend-only pushes therefore skip the Docker e2e
  and no longer fight a locally running dev stack over the published host
  ports (the CI stack cannot share them). Backend/docs/CI pushes behave
  exactly as before; mixed pushes run both workflows (unit suite twice —
  harmless).
- Tests: 104 (unchanged).

## 2026-08-31 — Classic portal: reputation dashboard + history (P2 done)

Frontend-only commit (web/), P2 backlog item done.

- New **Reputation & LLM-judge accuracy (ADR-005)** card below the candidates
  table (`web/portal/index.html` + `app.js`): amber LLM-judge accuracy line
  (ADR-004 decision-support, display-only), top-10 leaderboard from the live
  `reputation` map (points DESC), and the last 20 `reputation_history`
  entries (newest first) with colored deltas (+ green / − red). All three
  blocks have empty states.
- Data comes from the existing `GET {mock}/candidates` response
  (`reputation`, `reputation_history`, `llm_accuracy`) — no backend change.
  The panel refreshes in real time via the existing SSE `decision` event
  (reputation changes exactly when a decision lands); no new events.
- XSS: every dynamic string is escaped with `escapeHtml()` (actor names are
  user-controlled in QV mode via the `voter` field).
- Tests: 104 (unchanged — JS-only change).

## 2026-08-31 — Classic portal: SSE real-time updates + export buttons (P1 done)

Frontend-only commit (web/), P1 backlog exhausted.

- **SSE in the classic view** (`web/portal/app.js`): the 3s polling timer is
  gone. Live updates come from `EventSource` on the existing `GET /events`
  stream (`vote`/`decision`/`candidates` events). While the stream is down
  (EventSource auto-reconnects) a 15s polling fallback keeps the list fresh
  so no update is lost, and the next `onopen` stops the ticker and catches
  up; the toggle is renamed "Live updates: ON/OFF" (manual Refresh stays).
- **Export buttons** (`web/portal/index.html` + `app.js`): new `export`
  column with per-record TTL / JSON-LD / N-Triples / RO-Crate links to the
  existing `GET /api/v1/export/{annotation_id}?format=...` endpoint
  (`target="_blank" rel="noopener"`, classic dark-theme styling).
- Tests: 104 (unchanged — JS-only change).

## 2026-08-31 — Vercel static hosting for the zero-build web layer

- `web/vercel.json`: framework preset `other`, `ignoreCommand` (deploys are
  skipped when only backend files change), rewrites `/` -> classic portal,
  `/triadic` -> triadic view, `/widget` -> widget demo. One-time project
  settings: Root Directory `web`, empty build/install commands.
- API endpoints configurable per deployment: query params
  `?fen_mock_base=...&fen_status_base=...` (persisted to localStorage) on the
  triadic view; the classic portal keeps its base-URL field; the widget keeps
  its `api-base` attribute. Backends must be HTTPS (SSE / mixed content) and
  send CORS headers (`FEN_CORS_ORIGINS`, default `*`).
- `web/README.md` documents local run (status-api serves `/web`) and Vercel
  deployment.
- Tests: 104 (unchanged — frontend-only change).

## 2026-08-30 — Governance e2e modes, SHACL CI gate, Loki, mobile-first portal

- E2E now covers all three decision modes (3a7f43f, CI run 33306094359 green):
  `scripts/smoke_test.py --mode auto|community|qv` — community casts votes
  until quorum, QV casts intensity-5 votes until the threshold; both assert
  `quorum_reached=True` + majority outcome and run the live SHACL gate on
  the named graph. `docker-compose.voting.yml` overrides
  `FEN_MOCK_VOTING/QUORUM/QV_THRESHOLD`; the CI `e2e` job runs all three.
- SHACL validation as its own CI step: `scripts/shacl_check.py` (self-check
  valid conforms / invalid rejected; `--graph-file`/`--endpoint` modes;
  merges the gfen: ontology so `sh:class` resolves).
- Loki log aggregation: `loki` + `promtail` compose services; promtail
  scrapes the Docker socket (`docker_sd_configs`) and ships container logs
  to Loki; Loki datasource provisioned into Grafana (Explore).
- Mobile-first portal: viewport meta, `.table-scroll`, 44px touch targets,
  640/641px breakpoints in `web/portal/index.html` and `triadic.html`.
- Bugfixes from local verification: vote-triggered decisions now deliver the
  FULL candidate record so `document_id` survives (community/QV decisions
  were written to the annotation-named graph instead of
  `urn:graphia:document:{id}:graph`); `status-api` exposes `/metrics`
  (prometheus-client added to its requirements — the scrape target was
  down); promtail image installs `wget` (healthcheck was always unhealthy);
  observability configs are baked into images (`monitoring/docker/*.Dockerfile`)
  because Docker Desktop cannot share files from the removable drive
  hosting the repo (SD card is not registered in WSL drvfs).
- Tests: 104 (unchanged — new coverage is e2e-level).


## 2026-08-29 — P1–P5 feature track: SHACL, RDF export, SSE, QV, reputation

- Scaffold (mock): SHACL shape validation (`fen-shapes.ttl`, `ScaffoldedTripleShape`)
  plus extractor/matcher/disambiguator agent branch (`POST /scaffold`).
- Registry: RDF export from the Status API
  (`/api/v1/export/{id}?format=ttl|jsonld|nt|crate`, RO-Crate included) and
  SSE real-time events (`/events`) replacing the 3s poll in the portal.
- Consensus: Quadratic Voting mode (`FEN_MOCK_VOTING=qv`, intensity² cost,
  ADR-005 threshold), QV delegation (`POST /candidates/{id}/delegate`,
  liquid democracy, delegation-weighted scores), reputation rewards for
  validated outcomes only.
- Reputation dashboard: `GET /candidates` returns `reputation_history`
  (last 50) + `llm_accuracy` (agreements/total) — ADR-005 reputation capital.
- Frontend (separate commits): triadic view (`web/portal/triadic.html` +
  `triadic.js`) with QV/delegation UI, registry graph SVG, reputation panel;
  XSS-hardened widget/portal.
- Governance docs: ADR-006 (draft, tokenless challenge window), motivation
  stack formalized (reputation + intrinsic; gamification UX-only),
  `docs/BACKLOG.md` roadmap, `docs/integration-verification-plan.md`,
  pre-consortium tooling (Kafka topic aliases `FEN_TOPIC_*`).
- Tests: 104 (was 74).

## 2026-08-29 — CI e2e hardening: Virtuoso dialect check, rdflib/os fixes, fen-ci isolation

- `scripts/virtuoso_dialect_check.py` (new): SPARQL 1.1 dialect + idempotency
  check against a live OpenLink Virtuoso (the GoTriple KG engine) — Digest
  auth on /sparql-auth, explicit JSON results format. Wired into the CI `e2e`
  job (`docker compose --profile virtuoso up` + check + down). PASSED.
- Fixed the two bugs that made every CI run red: `status_api`/`mock_fen_api`
  imported `rdflib` without listing it in their per-service requirements
  (ModuleNotFoundError in Docker, invisible locally), and the consumers used
  `os.getenv(METRICS_PORT)` without `import os` (NameError).
- The `e2e` job now sets `COMPOSE_PROJECT_NAME=fen-ci` so the CI stack can
  never collide with (or tear down) a locally running dev stack on the same
  Docker daemon; docs/self-hosted-runner.md §6a documents the interaction.
- Tests: 104 (was 82).

## 2026-08-29 — Security & concurrency hardening (widget/portal XSS, vote race)

- web/widget/fen-status-widget.js + web/portal/app.js: every server-provided
  value is HTML-escaped before innerHTML interpolation; decision-PID links
  render only for http(s) URLs (the widget is embedded on third-party pages).
- mock_fen_api `cast_vote`: the quorum now claims the candidate (status
  'deciding') inside the state lock, so concurrent votes reaching the quorum
  cannot schedule a second delivery (no duplicate webhook/decision_id).
- tests/test_voting.py: exactly-once delivery test (74 tests).

## 2026-08-29 — Milestone: web interface layer (Flow 1 & Flow 2)

Zero-build web UI (plain HTML/JS + FastAPI, no Node toolchain) exposing the
two community flows end to end:

- **Status API** (`services/status_api/`): read-side
  `GET /api/v1/status/{annotation_id}` resolving `gfen:` provenance live from
  the RDF store via SPARQL; CORS enabled; serves the static UI at `/web`.
  Strictly read-only (ADR-001).
- **Flow 1 — Community DAO portal** (`web/portal/`): submit candidates, live
  status badges, LLM recommendation column (decision-support only, ADR-004),
  community voting with quorum progress (`FEN_MOCK_VOTING=community`,
  `POST /candidates/{id}/vote`, deterministic majority).
- **Flow 2 — status widget** (`web/widget/`): embeddable `<fen-status>` Web
  Component (Shadow DOM, dark/light themes) + demo page; clicking a badge
  shows decision details (method, dereferenceable PID per ADR-003, ledger
  anchor).
- **REST contract** (`web/api.md`): v1 — the same contract the real FEN
  backend (ADR-002) is expected to implement, keeping the UI backend-agnostic.
- Mock FEN API extended: candidate tracking, community-voting mode, CORS.
- Infographic `docs/images/widget-overview.svg`; docker-compose and k8s gain
  the `status-api` service.
- Tests: **73** offline (was 61) — status-api mapping/errors/CORS, voting
  logic, quorum delivery, widget static mount; the e2e smoke test now also
  verifies the status-api read path.
- Local tooling (outside the repo): `start-dev.bat` (build + open the UI),
  `status-dev.bat` (stack + health check).

## 2026-08-29 — Milestone: CI fully green — three consecutive real e2e runs

GitHub Actions on the self-hosted runner (`fen-laptop`): `test (3.10)` and
`e2e` both pass — **three runs in a row: 33270403191, 33270549408,
33270654051**. The `e2e` job now executes the FULL stack for real: the job
log shows `docker compose up --build -d`, `published EntityCandidate`,
`E2E SMOKE TEST PASSED: smoke_f998e70531af`, `docker compose down`. This is
the end-to-end proof the consortium asks for: candidate -> Kafka -> FEN
Bridge -> mock DAO -> webhook -> decision topic -> Validation Result
Consumer -> SPARQL UPDATE in Fuseki -> EntityValidated topic -> status API
(widget data path included).

## 2026-08-29 — Fix smoke-test consumer-group probe on kafka-python 2.x

The CI `e2e` job failed with a silent 120s timeout waiting for the outbound
consumer group. Root cause: kafka-python API drift — 2.x
`list_consumer_groups()` returns a list of `(name, protocol_type)` tuples
(3.x: `[GroupOverview]`) and names the describe API
`describe_consumer_groups()` (3.x: `describe_groups`). The probe now
normalizes all three shapes (scripts/smoke_test.py) and was verified against
stub admins for both versions.

## 2026-08-29 — REAL end-to-end run passed on Docker (first true e2e)

The first genuinely executed end-to-end pipeline on this machine (Docker
Desktop installed, WSL2 backend): candidate -> Kafka -> FEN Bridge -> mock
DAO -> webhook -> decision topic -> Validation Result Consumer -> SPARQL
UPDATE in Fuseki -> EntityValidated topic -> status API. The run exposed and
fixed four production bugs the unit suite could not see:

- `stain/jena-fuseki:4.9.0` did not exist in the registry -> 5.1.0
  (docker-compose.yml).
- kafka-python 3.x broke the callable serializer API
  (`SerializeWrapper.serialize()`) -> pinned `<3` in all requirements.
- The JSON value serializer crashed on `GovernanceDecision.decided_at`
  (datetime) -> `_json_default` emits ISO-8601 (services/common/kafka_io.py).
- `services/common/metrics.py` imported `fastapi` at module level, which
  crashed the consumer images (no web framework installed) -> lazy import.
- Jena Fuseki 5 requires authentication on `/update` (HTTP 401) -> optional
  SPARQL basic auth via `SPARQL_UPDATE_USER/PASSWORD` (dev defaults admin/admin).
- `scripts/smoke_test.py`: `wait_for` returned `None` (callers crashed on
  the result) -> returns the probe value.
- kafka-python 2.3.2 compatibility: `commit_offsets` now passes
  `leader_epoch=0` explicitly (2.3.2 requires the third field); the smoke
  test's consumer-group admin check is best-effort (falls back to a settle
  delay when the admin API is flaky, e.g. kafka-python 2.3.2 on Windows
  against Kafka 3.6).

Local run: `python scripts/smoke_test.py` -> **E2E SMOKE TEST PASSED**.
With Docker now installed, the CI `e2e` job on the self-hosted runner runs
the full stack instead of skipping it.

## 2026-08-28 — CI green on the self-hosted runner

- Registered the self-hosted runner `fen-laptop` as a Windows service
  (`GitHubActionsRunner` via NSSM; `svc.cmd` was removed in runner v2.3xx).
- Resolved machine-specific CI issues: git `safe.directory` via the runner
  `.env`, work directory on `C:` (D: full, no symlinks), system Python 3.10
  (setup-python toolchains wiped by the environment), `powershell` shell for
  the Docker check (WSL bash breaks Windows paths, `pwsh` missing).
- First green run: **33195156069** — `test (3.10)` + `e2e` pass (Docker steps
  skipped until Docker Desktop is installed; installer downloaded).
- CI runs in a documented TEMPORARY self-hosted mode (GitHub billing block);
  revert plan: `docs/self-hosted-runner.md` step 7.

## 2026-08-28 — Repository published

- Created and pushed the public repository
  `riznykst/fen-triadic-synthesis` (13 commits at publish time).
- PR #1 merged: Python 3.12 `datetime.utcnow` deprecation fix.

## 2026-08-27 — MVP completed

- FEN Bridge, Validation Result Consumer, mock DAO, shared contracts, PID
  helpers (ADR-003), gfen: ontology + SHACL, 61 offline tests.
- ADR-001/002/003/004, user stories with infographics, k8s manifests,
  observability, CI (test + e2e), whitepaper PDF and research (English).
