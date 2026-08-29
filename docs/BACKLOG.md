# BACKLOG — full development history and remaining work

Legend: `[x]` done · `[~]` partial · `[ ]` open. Snapshot: 2026-08-29.

## Delivered
- [x] MVP core: FEN Bridge (outbound + webhook), Validation Result Consumer, mock DAO, shared Pydantic contracts, Kafka topics, docker-compose stack
- [x] ADR-001..005: hash-only anchoring · federation node · PID scheme (ARK/w3id, g/v/r/s) · LLM decision-support · web layer
- [x] gfen: ontology + SHACL shapes; owl:imports stub documented (IRI pending)
- [x] PID helpers, JSON schemas generated from models, SHACL parse tests
- [x] Kafka delivery guarantees: acks=all, idempotent producer, commit-after-processing (at-least-once)
- [x] Security: webhook Bearer auth, no secrets tracked, k8s Secret placeholder
- [x] Observability: Prometheus /metrics, JSON logs, /readyz, graceful shutdown
- [x] CI: unit tests + REAL e2e on Docker — green for 5+ consecutive runs; self-hosted runner as a Windows service (NSSM)
- [x] e2e bug hunt: fuseki image tag, kafka-python 2.x/3.x compat (serializer, OffsetAndMetadata, admin API), datetime serializer, Fuseki basic auth, lazy fastapi import
- [x] Web layer: DAO portal (Flow 1) + status widget (Flow 2), community voting in the mock
- [x] Docs: README, architecture, user stories + infographics, whitepaper PDF, research (EN), CHANGELOG, self-hosted runner guide
- [x] Repository published: riznykst/fen-triadic-synthesis (public), 30+ commits

## In progress / partial
- [~] CI Python matrix on self-hosted: 3.10 only (setup-python toolchains get wiped); full 3.10/3.11/3.12 once back on hosted runners
- [~] Docker e2e: works locally and in CI; Docker Desktop installed on the dev machine
- [~] k8s manifests: present, not deployed anywhere yet

## Backlog
- [ ] Fix GitHub billing -> hosted runners, restore pull_request trigger + full matrix, remove the self-hosted runner (docs/self-hosted-runner.md step 7)
- [ ] Real GRAPHIA test instance: verify Kafka topic names, WP4 message schema, named-graph URI scheme, Virtuoso SPARQL dialect
- [ ] Register FEN NAAN + publish N2T/w3id redirects (ADR-003)
- [ ] Replace the owl:imports stub with the official GRAPHIA Ontology IRI
- [ ] Wire the real DAO/Quadratic Voting (replace the mock's rule); LLM judge stays decision-support only (ADR-004)
- [ ] Use LLM4SSH/Quagga as Agentic Scaffolding backends (provider already pluggable via FEN_LLM_*)
- [ ] SHACL validation step in CI
- [ ] Monitoring dashboard (Prometheus/Grafana) + log aggregation (Loki)
- [ ] Secrets management (vault) for non-local deployments
- [ ] e2e for the community-voting mode (portal Flow 1: /candidates + /vote end-to-end)
- [ ] Precision/recall evaluation before vs after community validation (consortium deliverable)
- [ ] Accessibility pass: mobile-first portal UI

## Known environment quirks (dev machine)
- D: nearly full (58.5/58.6 GB) -> runner work dir lives on C:
- WSL bash breaks Windows paths in Actions steps -> use the powershell shell
- actions/setup-python toolchains get wiped -> system Python on self-hosted
- Schannel blocked inside the harness sandbox -> the runner runs as a Windows service (outside the sandbox)
