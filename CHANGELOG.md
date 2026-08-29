## 2026-08-29 — Security & concurrency hardening (widget/portal XSS, vote race)

- web/widget/fen-status-widget.js + web/portal/app.js: every server-provided
  value is HTML-escaped before innerHTML interpolation; decision-PID links
  render only for http(s) URLs (the widget is embedded on third-party pages).
- mock_fen_api `cast_vote`: the quorum now claims the candidate (status
  'deciding') inside the state lock, so concurrent votes reaching the quorum
  cannot schedule a second delivery (no duplicate webhook/decision_id).
- tests/test_voting.py: exactly-once delivery test (74 tests).
# Changelog

All notable changes are recorded here in reverse chronological order.

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
