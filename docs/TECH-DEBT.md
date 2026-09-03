# Technical Debt Plan — audit 2026-09-02

> **Internal maintainer audit notes**; not part of the research artifact.

_Status: plan approved for execution; items below are the backlog of
maintenance work identified by the full-repo audit (5 parallel area reviews:
backend, infra/CI, web layer, docs/ontology, tests). Verified against HEAD
`d689ccd` (127 commits, 111 tests, CI green). Backend/infra/web findings were
re-verified on this tree after the D:-drive failure forced the repo home to
`C:\fen-triadic-synthesis`._

Legend: `[ ]` open · `[~]` partial · `[x]` done. Priorities:
P0 = correctness/reliability · P1 = consistency · P2 = quality/maintenance ·
P3 = structural.

## P0 — correctness / reliability

- [x] **outbound.py commits whole-consumer position** — `services/fen_bridge/outbound.py:48`
  calls `consumer.commit()` while the rest of the pipeline uses the shared
  per-record `commit_offsets(consumer, batch)` (`services/common/kafka_io.py`).
  A change to poll caps/batch truncation could silently downgrade
  at-least-once to at-most-once.
  Fix: route outbound through `commit_offsets`; update the `_FakeConsumer`
  double in `tests/test_fen_bridge.py`.
  DONE 2026-09-03 (in tree, commit pending): `commit_offsets(consumer, batch)`
  + per-record offset+1 asserted in `tests/test_fen_bridge.py`; pytest 111
  green.
- [~] **k8s manifests drift vs compose and fail open** —
  `k8s/configmap.yaml` points `FEN_API_BASE_URL` at `http://fen-api:8080`
  (no such service; compose/code use `mock-fen-api:8100`), Kafka at
  `kafka:9092` (compose container listener is `29092`), no
  `SPARQL_UPDATE_USER/PASSWORD` (compose sets admin/admin), deployments use
  `:latest` images, and `k8s/secret.yaml` holds the base64 of an EMPTY
  `FEN_WEBHOOK_TOKEN`. Deploying verbatim strands the pipeline silently
  (FenClient never raises → endless retries; unauthenticated SPARQL UPDATEs
  → 401 loop; forged webhook decisions accepted).
  Fix: one shared env source for compose + k8s; Secret with a real token;
  fail closed on empty token outside dev; pinned image tags +
  imagePullPolicy; add probes/metrics port to consumer deployments
  (`k8s/fen-bridge-outbound.yaml`, `k8s/validation-consumer.yaml`); align
  status-api labels (`app.kubernetes.io/name`).
  PARTIAL 2026-09-03 (in tree, commit pending): secret.yaml now carries
  intentionally INVALID base64 (kubectl apply refuses it — fail-closed);
  empty SPARQL creds removed from configmap (documented
  `kubectl create secret generic fen-sparql-credentials`); Kafka-listener
  and FEN_API_BASE_URL comments clarified; readiness/liveness probes +
  containerPort 9101/9102 on both consumer Deployments; stale "no HTTP
  port" comments fixed. OPEN: single env source, pinned image tags,
  status-api label alignment.
- [x] **Stale test counts (honesty contract)** — README `104 tests` in three
  places (badge line 8, layout line 234, CI section line 430), plus
  CONTRIBUTING and BACKLOG delivered items; the suite is **111**.
  Fix: update all occurrences (done for README/CONTRIBUTING 2026-09-02 —
  verify BACKLOG).
  DONE 2026-09-02: README (3×), CONTRIBUTING (2×), BACKLOG delivered item
  — all now say 111.
- [x] **Vercel `ignoreCommand` fragile on shallow history** — root
  `vercel.json` uses `git diff --quiet HEAD^ HEAD -- web/`; `HEAD^` fails on
  the first commit and under limited-history clones (degrades to
  always-deploy), and merge commits compare only the first parent.
  Fix: diff against `$VERCEL_GIT_PREVIOUS_SHA` with a build-on-error guard;
  document the file's actual location (repo root, not `web/`).
  DONE 2026-09-03 (in tree, commit pending): ignoreCommand =
  `git diff --quiet "${VERCEL_GIT_PREVIOUS_SHA:-HEAD^}" HEAD -- web/ 2>/dev/null || exit 1`
  — any diff error → deploy; clean diff → skip.

## P1 — consistency

- [x] **SSE live-update logic triplicated with three behaviors** — app.js,
  triadic.js and the widget each re-implement EventSource + fallback.
  triadic.js drifted: `onerror` starts the fallback only when the stream
  never opened (`if (!sseOk)`), `onopen` never catches up — a mid-session
  drop leaves Consensus/Registry silently stale (`web/portal/triadic.js:475-476`).
  Fix: unify semantics (onerror → always fallback; onopen → stop ticker +
  reload), then extract one shared helper.
  DONE 2026-09-03 (in tree, commit pending): new `web/shared/live.js`
  (`fenLive`) with unified semantics — fallback ticker while the stream is
  down, catch-up reload on every (re)open, named-frame dispatch; both
  portal views now use it (`app.js` startLiveUpdates, `triadic.js`); widget
  keeps its self-contained copy (embeddability) but documents mirroring the
  helper. Awaiting node --check.
- [x] **Last unescaped XSS surface in the portal** — `statusBadge()`
  interpolates the server `status` value unescaped into class + text;
  vote/quorum counters are interpolated raw and `c.votes` is dereferenced
  without a guard (`web/portal/app.js:59-61,108-109`).
  Fix: enum-validate + `escapeHtml` for status; `const votes = c.votes ||
  {}` + `Number()` coercion; prefer DOM/textContent row building.
  DONE 2026-09-03 (in tree, commit pending): `VALID_STATUSES` enum +
  escaped class/text; `votes = c.votes || {}` + `Number()` coercion.
  Awaiting node --check when the harness shell is stable.
- [x] **URN/IRI/NAAN duplication** — `_annotation_uri()` copy-pasted
  (`sparql_updater.py`, `status_api/main.py`), gfen predicate IRIs hardcoded
  as literals in `_PREDICATE_KEYS` (drift risk vs
  `services/common/gfen_ontology.py`), `fen_naan` declared but never read in
  both `FenBridgeConfig` and `ValidationConsumerConfig`, NAAN default
  `"99999"` triplicated (`fen_bridge/config.py`, `validation_consumer/config.py`,
  `services/common/pid.py`).
  Fix: centralize annotation-URI/named-graph helpers and predicate constants
  in `services/common`; drop dead `fen_naan` fields.
  DONE 2026-09-03 (in tree, commit pending): new
  `services/common/graph_uris.py` (annotation_uri/document_graph_uri/
  annotation_graph_uri) used by sparql_updater, validation-consumer
  (`named_graph_uri`) and status-api; `_PREDICATE_KEYS` built from
  `gfen_ontology.PROP_*`; dead `fen_naan` fields removed from both configs.
- [x] **Kafka JSON schemas not guarded against model drift** —
  `schemas/kafka-events/*.json` are generated from the Pydantic models and
  are in sync today, but nothing enforces freshness
  (`tests/test_messages.py:66` only checks well-formedness).
  Fix: test regenerating each schema in memory and asserting equality with
  the committed file (or CI diff on `scripts/generate_schemas.py`).
  DONE 2026-09-03 (in tree, commit pending):
  `test_committed_kafka_schemas_match_models` in tests/test_messages.py
  (expect suite 111 → 112).
- [~] **Five near-identical Dockerfiles + no `.dockerignore`** — same
  `FROM python:3.11.9-slim-bookworm` + pip layer repeated; each image COPYs
  the whole `services/` tree; no `.dockerignore` (context ships `.git`,
  `__pycache__`, `.pytest_cache`, a local `.env` if present);
  `prometheus-client` pins drifted (`>=0.20` vs `>=0.19`);
  `validation_consumer/requirements.txt` carries unused `rdflib`.
  Fix: shared base stage + thin per-service final stages (or ARG-driven
  Dockerfile), root `.dockerignore`, single-source requirements,
  aligned pins.
  PARTIAL 2026-09-03 (in tree, commit pending): root `.dockerignore`
  added (.git/__pycache__/.pytest_cache/.env/docs/tests/.vendor excluded).
  OPEN: base-stage consolidation, requirements single-sourcing, pin
  alignment (needs image builds).
- [ ] **Virtuoso image floating** — `openlink/virtuoso-opensource-7`
  unpinned while CI e2e boots it on every push
  (`docker-compose.yml:218`); a breaking upstream tag changes the e2e
  baseline.
  Fix: pin tag or digest in one place used by compose + dialect check.
- [~] **Compose healthcheck gaps** — fuseki (no healthcheck) while
  status-api/validation-consumer `depends_on` it with `service_started`;
  outbound/validation-consumer (each serves /metrics on 9101/9102) and
  zookeeper have no healthchecks; compose status-api lacks
  `SPARQL_PING_ENDPOINT` so `/readyz` is always "degraded" locally.
  Fix: add healthchecks (fuseki `/$/ping`, consumers `/metrics`, zookeeper),
  switch depends_on to `service_healthy`, set `SPARQL_PING_ENDPOINT:
  http://fuseki:3030/$/ping`, probe `/readyz` in the compose healthcheck.
  PARTIAL 2026-09-03 (in tree, commit pending): outbound + validation-consumer
  healthchecks on /metrics (python probe, ports 9101/9102);
  `SPARQL_PING_ENDPOINT` set for status-api (readyz no longer degraded).
  OPEN: fuseki/zookeeper healthchecks (need image-content check), switching
  depends_on to `service_healthy`, probing `/readyz` in compose.

## P2 — quality / maintenance

- [ ] **Web layer consolidation** — `escapeHtml` implemented three times
  under three names (`app.js`, `triadic.js` esc/jsAttr, widget); API-base
  convention implemented four divergent ways (query → localStorage → default
  vs snapshotted consts vs attribute-only vs demo param); the light palette
  re-theme landed only in `index.html` while triadic.html/triadic.js/widget
  hard-code their own hex families; three incompatible badge systems
  (`.b-<status>` vs `.b-<color>` vs widget COLORS); dark/light leftovers
  (SVG forced white, widget dark default, demo.html dark) with no
  `prefers-color-scheme`.
  Fix: one shared zero-dependency `web/shared/` module (escape, tokens CSS,
  status→color map, apiBase convention); align widget default with the light
  portal.
- [~] **Accessibility (a11y)** — form controls without `for`/`id` pairing,
  table without `<caption>`/`scope="col"` (`web/portal/index.html`,
  `triadic.html`); widget expand control is a `<div>` (not focusable, no
  role/aria-expanded/keydown); triadic ± / delegate buttons are symbol-only
  without aria-labels.
  Fix: label/for everywhere, caption + scope, real `<button>` semantics +
  aria in widget, aria-labels on icon buttons.
  PARTIAL 2026-09-03 (in tree, commit pending): labels paired with for/id in
  both portal pages; table caption + scope="col"; widget expand control is a
  real button with aria-expanded + focus-visible, "retry" is a button.
  OPEN: aria-labels on the triadic ± / delegate symbol buttons.
- [~] **Dead code** — `poll_batch` (values-only) + its shim export and test
  (superseded by `poll_batch_with_offsets`); `renderGraphSvg`, `regGraph`
  refs and the graph dispatcher + unused `OUTCOME_BG` (`triadic.js`);
  write-only `_sseOk` flags (`app.js`, widget); duplicate SSE error binding
  in the widget (server `event: error` vs transport onerror conflated);
  orphaned mid-function docstring in `webhook.py`; `_broadcast` swallows
  `queue.Full` with `pass` (events silently dropped for slow subscribers).
  PARTIAL 2026-09-03 (in tree, commit pending): `poll_batch` deleted
  (module + shim + compat test); webhook.py docstrings merged; `_broadcast`
  logs + evicts full subscribers. OPEN: triadic.js renderGraphSvg/regGraph/
  OUTCOME_BG, widget _sseOk + duplicate error binding.
- [~] **Config hygiene** — `batch_size=10`/`poll_timeout_ms=1000`/group id
  hardcoded in `validation_consumer/main.py` (fen_bridge equivalents are
  env-driven); SPARQL timeouts hardcoded (`timeout=10.0/5.0`) in status-api
  despite an env config dataclass; HTTP status derived by substring-matching
  error prose in `delegate_vote` (`mock_fen_api/main.py:539`).
  Fix: env knobs via `from_env()`; structured error result from
  `apply_delegation`.
  PARTIAL 2026-09-03 (in tree, commit pending):
  `FEN_CONSUMER_GROUP_ID/BATCH_SIZE/POLL_TIMEOUT_MS` env knobs;
  `SPARQL_TIMEOUT_S`/`SPARQL_PING_TIMEOUT_S` env knobs. OPEN:
  `apply_delegation` structured error result.
- [~] **Test blind spots** — `FenClient` (designed to swallow errors and
  retry — its whole failure mode is unverified) has no unit tests;
  `delegation.py` exercised only indirectly; no linting/formatting config
  anywhere; 1616 pytest warnings un-triaged.
  Fix: FenClient unit tests (success/retry/terminal-failure), direct
  delegation tests, add ruff/flake8 config, triage warnings (rdflib
  deprecations, datetime.utcnow).
  PARTIAL 2026-09-03 (in tree, commit pending): new `tests/test_fen_client.py`
  (4 tests: success / transient-retry-with-backoff / terminal-failure-returns-
  False / HTTP-4xx-as-failure). OPEN: direct delegation tests, linter config,
  warning triage (rdflib deprecations in test_qv_scaffold/test_sparql_updater).
  LATER 2026-09-03 (in tree, commit pending): `pyproject.toml` with a
  conservative [tool.ruff] preset added (F/E9/B/BLE + per-file ignores) —
  first `ruff check` run still pending.
- [ ] **Metrics collision** — `fen_kafka_messages_processed_total` /
  `_failed` emitted by BOTH fen-bridge-outbound and validation-consumer
  with no distinguishing labels; the Grafana dashboard plots the two series
  under one legend.
  Fix: add a `process`/`service` label (or per-process metric names).
- [x] **Docs drift (architecture/status)** — `docs/architecture.md`:
  observability table claims consumers expose no /metrics (they serve
  9101/9102), k8s section lists 3 Deployments (status-api exists), "four
  ADRs" (six exist), duplicated sentence fragment; `docs/self-hosted-runner.md`:
  claims ci.yml uses ubuntu-latest (it is self-hosted) + stale PUBLIC
  banner (repo private); BACKLOG: "72 commits" (125), self-contradictory
  public/private note, snapshot date stale, Node-availability contradiction
  in the UI-e2e item; ADR-005: decision list jumps 4→6 and cites draft
  ADR-006 as settled.
  Fix: rewrite the /metrics + k8s sections to match code; extend
  self-hosted-runner step 7 with the concrete ci.yml edits; reconcile
  counts/visibility/Node; renumber ADR-005 decisions and soften ADR-006
  references to "if accepted".
  DONE 2026-09-03 (in tree, commit pending): architecture.md observability +
  k8s sections rewritten (5 processes with /metrics ports, 4 Deployments,
  fail-closed Secret docs, ADR-001..006, dup fragment removed);
  self-hosted-runner step 5/7 rewritten + counts 111→115 + 0xFF chars
  fixed; ADR-005 renumbered 1..5 with "IF ADR-006 is accepted". (The
  PUBLIC banner was left as-is: the repo is PUBLIC again as of 2026-09-03;
  BACKLOG counts/visibility were already reconciled 2026-09-02.)

## P3 — structural

- [ ] **Retire the TEMPORARY self-hosted CI mode** — ci.yml: matrix reduced
  to system Python 3.10 while images ship 3.11; Windows-only idioms
  (`shell: powershell`, `cmd /c`, `$env:GITHUB_OUTPUT`) in steps that would
  break on ubuntu-latest; e2e "passes" silently when Docker is unavailable
  (steps skipped); `web.yml` duplicates the test job for web-only pushes.
  Fix (when billing is fixed): restore `runs-on: ubuntu-latest` +
  `pull_request` + matrix 3.10/3.11/3.12 + setup-python; remove the
  powershell overrides; make e2e fail (not skip) without Docker; merge
  web.yml back.
- [ ] **Single env source for compose + k8s** — generate `k8s/configmap.yaml`
  from the same definitions docker-compose uses (see P0 k8s item).
- [ ] **JS-level testing/a11y automation** — revisit once the Node
  availability question is settled (BACKLOG P3 "UI e2e test").

## Clean (verified during audit — not debt)

- ADR-006 gating is consistent everywhere (widget render, status-api
  `_PREDICATE_KEYS`, BACKLOG/README wording; nothing writes
  `challengeWindowEnd`).
- Ontology ↔ shapes consistent: every class/property referenced by
  `fen-shapes.ttl` is defined in `fen-ontology.ttl`; the `owl:imports` stub
  IRI is documented consistently.
- No bare `except:`; all broad handlers log; BACKLOG `[x]` items all backed
  by code/CHANGELOG/commits.
- Kafka JSON schemas currently in sync with the Pydantic models.
- Compose healthchecks verified sound for grafana/loki/prometheus/promtail
  (wget present in images).
- CI run 33678903368 (d689ccd): test + e2e green, all steps executed.

## Environment note (2026-09-02)

The D: SD-card failed mid-audit: the working tree at
`D:\FEN-GRAPHIA\fen-triadic-synthesis` became 0xFF placeholders (repo,
`.gitconfig`, FEN-SYNC.md all corrupted). Recovery state:
repo home `C:\fen-triadic-synthesis` (HEAD d689ccd), runner
`C:\actions-runner` (service GitHubActionsRunner running), work dir
`C:\fen-runner-work`, sync tooling `C:\FEN-GRAPHIA\fen_sync_check.py` →
`C:\FEN-GRAPHIA\FEN-SYNC.md`, venv `C:\fen-venv`, salvage copy
`C:\fen-salvage`. All tools/docs that still reference D: paths are debt
items themselves — update as encountered.
