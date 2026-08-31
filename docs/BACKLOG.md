# BACKLOG — full development history and remaining work

Legend: `[x]` done · `[~]` partial · `[ ]` open. Snapshot: 2026-08-30 (prioritised).

## Delivered
- [x] MVP core: FEN Bridge (outbound + webhook), Validation Result Consumer, mock DAO, shared Pydantic contracts, Kafka topics, docker-compose stack
- [x] ADR-001..006: hash-only anchoring · federation node · PID scheme (ARK/w3id, g/v/r/s) · LLM decision-support · participation/QV (ADR-005) · tokenless challenge window draft (ADR-006)
- [x] gfen: ontology + SHACL shapes; owl:imports stub documented (IRI pending)
- [x] PID helpers, JSON schemas generated from models, SHACL parse tests
- [x] Kafka delivery guarantees: acks=all, idempotent producer, commit-after-processing (at-least-once)
- [x] Security: webhook Bearer auth, no secrets tracked, k8s Secret placeholder
- [x] Observability: Prometheus /metrics (all 5 processes), JSON logs, /readyz, graceful shutdown
- [x] CI: 104 unit tests + REAL e2e on Docker — green for consecutive runs; self-hosted runner as a Windows service (NSSM); runner paused during local demos (runs queue, no stack teardown)
- [x] CI e2e: Virtuoso dialect check (`scripts/virtuoso_dialect_check.py`, OpenLink Virtuoso, Digest auth, idempotency) wired into the `e2e` job
- [x] CI isolation: `COMPOSE_PROJECT_NAME=fen-ci` — the CI stack can never collide with or tear down a local dev stack on the same Docker daemon (self-hosted-runner.md §6a)
- [x] e2e bug hunt: fuseki image tag, kafka-python 2.x/3.x compat (serializer, OffsetAndMetadata, admin API), datetime serializer, Fuseki basic auth, lazy fastapi import; rdflib in per-service requirements; `import os` in consumers
- [x] Web layer: DAO portal (Flow 1) + status widget (Flow 2), community voting in the mock
- [x] Triadic view (Scaffold → Consensus → Registry): POST /scaffold (LLM + heuristic fallback, ADR-004), QV voting mode (FEN_MOCK_VOTING=qv, weighted scores, FEN_MOCK_QV_THRESHOLD=10), reputation (ADR-005: +2 author / +1 validators), registry graph (SVG), SSE real-time, RDF export, delegation (liquid democracy)
- [x] QV hardening: one-vote-per-voter, reputation only for validated records, API error details (409), stored-XSS fix in the portal
- [x] Motivation stack formalized: reputation capital + intrinsic motivation; gamification is UX-only, never core mechanics (f9356ec)
- [x] Docs: README, architecture, user stories + infographics, whitepaper PDF, research (EN), CHANGELOG, self-hosted runner guide; README/CHANGELOG/.env.example audited against the repo state (2026-08-29)
- [x] Repository published: riznykst/fen-triadic-synthesis (private at the owner's request; public), 72 commits
- [x] P1 bundle shipped (3a7f43f, CI run 33306094359 green): e2e for community/QV voting (`smoke_test.py --mode community|qv` + `docker-compose.voting.yml`), SHACL validation as a CI step (`scripts/shacl_check.py`), Loki log aggregation (promtail + Loki datasource in Grafana), mobile-first portal (index/triadic 640/641px breakpoints, 44px touch targets)
- [x] Vercel static hosting for the zero-build web layer (`web/vercel.json`: framework `other`, `ignoreCommand` skips deploys when only backend files change, rewrites `/`, `/triadic`, `/widget`; auto-deploy on push; API base config via query params/localStorage; `web/README.md`)
- [x] Bugfixes found by the new e2e modes: vote-triggered decisions lost `document_id` (consumer fell back to the annotation-named graph) — the full candidate record is now delivered; `status-api` exposes `/metrics` (target was down); observability configs baked into images (`monitoring/docker/*.Dockerfile`) because Docker Desktop cannot share files from the removable drive hosting the repo

## In progress / partial
- [~] CI Python matrix on self-hosted: 3.10 only (setup-python toolchains get wiped); full 3.10/3.11/3.12 once back on hosted runners
- [~] Docker e2e: works locally and in CI (incl. the optional Virtuoso profile); Docker Desktop installed on the dev machine
- [~] k8s manifests: present, not deployed anywhere yet
- [~] Virtuoso SPARQL dialect: verified against a local OpenLink Virtuoso container (dialect check in CI); the live GRAPHIA store is still pending

## Backlog (prioritised 2026-08-30)

**P1 — local, quick wins**
- [x] e2e for the community/QV voting mode (the smoke test currently exercises only `auto`) — DONE (3a7f43f): `--mode community|qv`, quorum/QV-threshold asserts, live SHACL gate
- [x] SHACL validation as a CI step (SHACL at Scaffold already exists backend-side) — DONE (3a7f43f): `scripts/shacl_check.py` step in the `test` job
- [x] Loki: log aggregation (Prometheus + Grafana metrics are already done) — DONE (3a7f43f): promtail (docker_sd_configs) → Loki 3.2.2, datasource provisioned
- [x] Mobile-first adaptation of the portal — DONE (3a7f43f): viewport meta, `.table-scroll`, 640/641px media queries
- [ ] SSE real-time in the CLASSIC portal (`web/portal/app.js` still polls every 3 s — the triadic view already has SSE)
- [ ] Export buttons (TTL / JSON-LD / N-Triples / RO-Crate) in the classic table view (`app.js`/`index.html`) — the `/export` endpoint exists

> **Recommended next P1 bundle:** SSE in the classic portal → export buttons in the classic table
> (CI↔host port isolation is already DONE via `COMPOSE_PROJECT_NAME=fen-ci`).

**P2 — external-ish, prepared locally**
- [ ] Register FEN NAAN + publish N2T/w3id redirects (ADR-003) — submission drafts ready in the working folder (outside the repo)
- [ ] Replace the owl:imports stub with the official GRAPHIA Ontology IRI
- [ ] Use LLM4SSH/Quagga as Agentic Scaffolding backends (provider already pluggable via FEN_LLM_*)
- [ ] Secrets management (vault) for non-local deployments
- [ ] Design unification: classic portal in the triadic view's style (light cards)
- [ ] Flow 2 widget: SSE real-time status + `gfen:challengeWindowEnd` (once ADR-006 lands)
- [ ] Reputation dashboard + history in the classic view (currently triadic-only)
- [ ] Widget embedding example page for dataset owners
- [ ] i18n (RU/EN) of the interface

**P3 — consortium/production**
- [ ] Fix GitHub billing -> hosted runners, restore pull_request trigger + full matrix (3.10/3.11/3.12), remove the self-hosted runner (self-hosted-runner.md step 7)
- [ ] Real GRAPHIA test instance: verify Kafka topic names, WP4 message schema, named-graph URI scheme, Virtuoso SPARQL dialect (local OpenLink check done)
- [~] Real DAO/Quadratic Voting contract + on-chain anchoring: mock QV mode done; production contract pending (ADR-001/ADR-004)
- [ ] Precision/recall evaluation before vs after community validation (consortium deliverable)
- [ ] Challenge window (ADR-006, reputation-lock) in the mock — after ADR-006 is accepted
- [ ] UI e2e test (no Node.js available in the sandbox)
- [ ] PID resolution as a CI step (once the NAAN is registered)
## Known environment quirks (dev machine)
- D: nearly full (58.5/58.6 GB) -> runner work dir lives on C:
- WSL bash breaks Windows paths in Actions steps -> use the powershell shell
- actions/setup-python toolchains get wiped -> system Python on self-hosted
- Schannel blocked inside the harness sandbox -> the runner runs as a Windows service (outside the sandbox)

## Flow roadmap (Scaffold → Consensus → Registry) — Top-10 recommendations

> **Implemented 2026-08-29:** #1 SSE real-time (backend + triadic view) ·
> #2 SHACL at Scaffold (pyshacl, ScaffoldedTripleShape) · #3 QV delegation
> (Liquid democracy, ADR-005 d.2) · #5 multi-agent scaffold (extractor/
> matcher/disambiguator) · #6 registry graph (SVG, zero-build) · #9 RDF
> export (ttl/jsonld/nt/crate) · #10 reputation dashboard (history +
> LLM-vs-DAO accuracy). Skipped: #7 (staking conflicts ADR-005 — ADR-006
> needed), #4/#8 (P3, external identity/ledger). ADR-006 draft (tokenless challenge window) in docs/adr/.

Priorities: P1 = quick wins on current code · P2 = medium effort, no external deps ·
P3 = needs external/production pieces (identity, ledger, consortium).

| # | Recommendation | Priority | Notes / conflicts |
|---|---|---|---|
| 1 | Real-time updates: SSE/WebSockets in mock_fen_api + status_api (replace 3s polling) | P1 | FastAPI `StreamingResponse`; also fixes the textarea-lost-on-poll UX issue |
| 2 | SHACL validation at Scaffold phase (fen-shapes.ttl) | P1 | Reuse `docs/ontology/fen-shapes.ttl`; backend check in `/scaffold` before voting; ties to "SHACL step in CI" item |
| 3 | Vote delegation (Liquid Democracy) | P2 | Already hinted in ADR-005 decision 2; delegation map + weight propagation in `qv_scores` |
| 4 | DID / Verifiable Credentials / Gitcoin Passport (sybil resistance) | P3 | Production-critical per ADR-005; MVP can stub an identity-provider interface (`voter` → verified identity) |
| 5 | Multi-agent cross-check at Scaffold (Extractor → Ontology Matcher → Disambiguator) | P2 | Fits the pluggable LLM provider (`FEN_LLM_*`); Matcher = SPARQL lookup, Disambiguator = Wikidata/GeoNames links |
| 6 | Graph visualization in Registry (Cytoscape.js / vis-network) | P2 | Zero-build constraint: vendor the lib; shows accepted triple linked into the KG |
| 7 | Challenge / dispute timelock window | P2 | **Conflicts with ADR-005 "no token economy"** if staking-based; alternative: reputation-lock (non-token) challenge; `gfen:disputed` flow already exists — needs ADR-006 if staking |
| 8 | Ledger verification modal in Registry | P3 | `ledgerAnchor` is `0xMOCK` until real anchoring (ADR-001) — verify modal ships with the real DAO/ledger work |
| 9 | Export accepted records: JSON-LD, Turtle, N-Triples, RO-Crate | P1 | `rdflib` serializers + a `/export` endpoint; strengthens the interoperability thesis |
| 10 | Reputation dashboard & community analytics | P2 | History tracking needed (current API exposes only live scores); LLM-vs-DAO precision/recall uses existing counters |