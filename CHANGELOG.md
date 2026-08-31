# Changelog

All notable changes are recorded here in reverse chronological order.

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
