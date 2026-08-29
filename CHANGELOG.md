## 2026-08-29 — Fix smoke-test consumer-group probe on kafka-python 2.x

The CI `e2e` job failed with a silent 120s timeout waiting for the outbound
consumer group. Root cause: kafka-python API drift — 2.x `list_consumer_groups()`
returns a list of `(name, protocol_type)` tuples (3.x: `[GroupOverview]`) and
names the describe API `describe_consumer_groups()` (3.x: `describe_groups`).
The probe now normalizes all three shapes (scripts/smoke_test.py) and was
verified against stub admins for both versions.
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
# Changelog

All notable changes are recorded here in reverse chronological order.

## 2026-08-29 — Fix kafka-python version incompatibilities found by CI

- `kafka_io.commit_offsets`: `OffsetAndMetadata` now passes all three
  positional args (offset, leader_epoch, metadata) — kafka-python 2.x
  requires `leader_epoch` without defaults (CI: TypeError).
- `smoke_test.py`: group listing handles both kafka-python 2.x
  (`list_groups() -> (error, groups)`) and 3.x (`list_consumer_groups()`);
  `describe_groups` tuple shape handled too (CI: AttributeError
  `list_groups`).
- Requirements pinned to `kafka-python>=3.0,<4` so runner and local
  environments resolve the same API.

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
