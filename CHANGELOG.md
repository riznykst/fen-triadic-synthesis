# Changelog

All notable changes are recorded here in reverse chronological order.

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
