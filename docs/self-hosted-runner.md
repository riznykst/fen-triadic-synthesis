# Self-hosted GitHub Actions runner (billing-block workaround)

> **Maintainer ops documentation** - machine-specific paths and run history; not part of the research artifact.

**Purpose.** While the GitHub account's Actions jobs are blocked by the
*"recent account payments have failed or your spending limit needs to be
increased"* billing flag, a **self-hosted runner** lets CI (unit tests + the
end-to-end smoke test) run on your own machine for free — self-hosted runners
do not consume GitHub-hosted minutes.

> ⚠️ **Security warning — this repository is PUBLIC.** A self-hosted runner
> executes workflow code on your machine. Anyone who can open a pull request
> can, in principle, get code executed on a runner attached to a public repo
> (GitHub-hosted runners are sandboxed; your machine is not). While the
> self-hosted runner is active, CI is restricted to **push events only** (see
> step 5) so fork PRs cannot trigger it. Revert to GitHub-hosted runners and
> remove the self-hosted runner as soon as the billing issue is resolved.

## Prerequisites (Windows)

- Git for Windows (already installed).
- Docker Desktop **running** for the `e2e` job (it runs `docker compose up`
  + `scripts/smoke_test.py`; Kafka/Fuseki containers are needed).
- Internet access from the runner (actions/setup-python downloads the Python
  toolchains automatically — no manual Python install required).
- The machine must be powered on while CI runs.

## Steps

### 1. Register the runner

Open the repo → **Settings → Actions → Runners → New self-hosted runner** →
choose **Windows / x64**. The page shows the registration token and download
URL (e.g. `actions-runner-win-x64-2.3xx.x.zip`).

### 2. Download and extract

```powershell
cd C:\actions-runner          # any directory, e.g. C:\actions-runner
Invoke-WebRequest -Uri https://github.com/actions/runner/releases/download/v2.3xx.x/actions-runner-win-x64-2.3xx.x.zip -OutFile runner.zip
Expand-Archive -Path runner.zip -DestinationPath . -Force
```

### 3. Configure

```powershell
./config.cmd --url https://github.com/riznykst/fen-triadic-synthesis --token <REGISTRATION_TOKEN>
```

Accept the defaults: group `Default`, runner name e.g. `fen-laptop`, work
folder `_work`.

### 4. Start

Foreground (for a test run):

```powershell
./run.cmd
```

Autostart as a Windows service (elevated PowerShell):

```powershell
./svc.cmd install
./svc.cmd start
```

### 5. Point the workflow at the runner

`.github/workflows/ci.yml` currently uses `runs-on: ubuntu-latest`
(GitHub-hosted only). While the billing block is active, change **both jobs**
to:

```yaml
runs-on: self-hosted
```

and restrict the triggers to pushes only (security, see warning above):

```yaml
on:
  push:
    branches: [main]
```

(drop `pull_request:` during the self-hosted period). Add a comment that this
edit is **temporary** and must be reverted with the billing fix.

### 6. Verify

Push the ci.yml change (or use **Re-run jobs** on an existing run). The job
log header shows `Running on fen-laptop`. Watch with:

```powershell
gh run watch --repo riznykst/fen-triadic-synthesis
```

Notes:

- The `e2e` job needs Docker Desktop running; the first `docker compose up
  --build` is slow (image pulls).
- actions/setup-python downloads Python 3.10/3.11/3.12 into the runner cache
  on first use.
- The Windows runner carries the labels `self-hosted`, `Windows`, `X64` —
  `runs-on: self-hosted` matches it.

### 6a. CI vs. the local dev stack (same Docker daemon)

The runner runs on the same machine where the developer's `docker compose
up` stack lives. Both used to share the default compose project name
`fen-triadic-synthesis`, so a CI `docker compose down` would tear down the
developer's local containers (and vice versa — a running local stack would
sabotage the CI e2e job). Since the Observability/P1 commits the `e2e` job
sets `COMPOSE_PROJECT_NAME: fen-ci`, so:

- CI containers/networks are `fen-ci-*` and never touch local ones;
- if the local stack holds the published ports (3030/8082/8100/8101/8890/
  9092/9090/3000), the CI "Start the stack" step fails fast with *"port is
  already allocated"* — the local stack is left untouched;
- to make CI pass, stop the local stack first (or run it on different ports):

```powershell
docker compose --profile virtuoso down   # from the repo directory
```

Forgetting to stop the local stack is safe (nothing gets deleted), just
red — the error message names the conflicting port.

### 7. Revert when billing is fixed

1. Restore `runs-on: ubuntu-latest` in both jobs.
2. Restore the `pull_request:` trigger.
3. Remove the runner: **Settings → Actions → Runners → ⚙ → Remove**.
4. Re-run the failed workflows: `gh run rerun` or a fresh push.

## Operational state (2026-08-28)

| Item | Value |
|---|---|
| Runner | `fen-laptop` — registered, **online**, "Listening for Jobs" |
| Service | `GitHubActionsRunner` (NSSM) — Running, Automatic, auto-restart. `svc.cmd` was removed in runner v2.3xx; NSSM is the official replacement |
| Runner dir | `C:\actions-runner` (outside the repo) |
| Work dir | `C:\fen-runner-work` — D: is full and does not support symlinks |
| Git fix | `.env` → `GIT_CONFIG_GLOBAL` pointing to a config with `safe.directory = *` (D: is FAT; git sees every directory as "dubious ownership") |
| Python | system `C:\Python310` (actions/setup-python toolchains get wiped by this environment; matrix reduced to 3.10 — TEMPORARY) |
| Shell for docker check | `powershell` (System32): `bash` resolves to WSL bash (breaks Windows paths), `pwsh` is not in the runner PATH |

Service management:

```powershell
C:\nssm\nssm-2.24\win64\nssm.exe stop GitHubActionsRunner
C:\nssm\nssm-2.24\win64\nssm.exe start GitHubActionsRunner
C:\nssm\nssm-2.24\win64\nssm.exe remove GitHubActionsRunner confirm
```

## Run history (2026-08-28)

| Run | Result | Note |
|---|---|---|
| 33187635656 | failure | GitHub billing block (hosted runners) |
| 33188502792 | cancelled | queued — no runner registered yet |
| 33190210343 | failure | checkout: git "dubious ownership" (D: FAT) |
| 33192311682 | failure | disk full on D: + setup-python toolchain wiped |
| 33194594709 | failure | e2e: WSL bash cannot read Windows-path scripts |
| 33194863876 | failure | e2e: `pwsh` not resolvable in runner PATH |
| **33195156069** | **success** | **test (3.10) + e2e green** (Docker steps skipped — no Docker) |

The green run proves the whole loop on this machine: checkout, dependency
install, 61 unit tests, import/RDF checks, e2e job logic. Docker Desktop
installer is downloaded to `C:\Users\Dell latitude 5480\Downloads\DockerDesktopInstaller.exe`;
once Docker runs, the e2e job automatically switches to the full stack
(Kafka + Fuseki + pipeline via `scripts/smoke_test.py`) — no CI change needed.

## Run history (2026-08-30)

| Run | Result | Note |
|---|---|---|
| 08:52�08:54 UTC | success | test + e2e green (auto smoke, SHACL CI step, Loki stack up) |
| 10:17 UTC + | running | commit 3a7f43f � community/QV voting e2e + SHACL + Loki + mobile portal |

## Environment notes (2026-08-30)

- **Docker Desktop file sharing is broken for D:** � the repo lives on an SD
  card (Realtek PCIE Card Reader, exFAT, DriveType=Removable). WSL automounts
  fixed drives only, so `/mnt/d` never exists and Docker Desktop never
  registers D: in `/run/desktop/mnt/host` � bind mounts from D: show files
  as empty directories (`drwxr-xr-x ... prometheus.yml`). C: mounts work.
  Workaround: **observability configs are baked into images**
  (`monitoring/docker/*.Dockerfile`) � no host bind mounts in the stack,
  CI and local dev behave identically.
- `settings-store.json` (`%APPDATA%\Docker`) was edited to add
  `"UseGrpcFuse": false` (falls back to the plan9 file-sharing daemon).
  Write the file WITHOUT a UTF-8 BOM � Docker's JSON parser crashes on BOM
  (`invalid character '\u00c3\u00af'`) and the backend exits with status 2.
- A `wsl --shutdown` + Docker Desktop restart does NOT fix the missing D:
  share; a manual `mount -t drvfs D: /mnt/d` inside WSL works, but Docker
  Desktop's own share table is separate and still misses D:.
- Re-running `docker compose up -d` recreates the whole stack (fresh
  Fuseki in-memory/TDB2 state) � expected; smoke tests tolerate it.
- promtail healthcheck reports "starting" until its first scrape batch �
  Loki ingestion verified by querying `/loki/api/v1/labels`.
## Working protocol (all chats, 2026-09-02)

Operating model agreed across the AI working chats (this repo has several
parallel AI sessions plus the Google Jules bot, which opens PRs) and the owner.

1. **Offline development loop (no Docker).** Most business logic is fully
   mocked and covered offline: `pytest -q` (111 tests - Kafka schemas, SPARQL
   UPDATE generator, QV logic, PID helpers, FastAPI handlers, SSE), plus
   `python scripts/generate_schemas.py` and `python scripts/shacl_check.py`.
   `node --check` for web-layer JS. ~90% of bugs are caught here.
2. **E2E is automatic, not manual.** Every push to `main` runs CI on the
   self-hosted runner; the `e2e` job boots the real stack
   (`COMPOSE_PROJECT_NAME=fen-ci`): Kafka/Fuseki (+ optional Virtuoso profile)
   -> `scripts/smoke_test.py` (auto/community/QV) -> Virtuoso dialect check ->
   teardown. Prerequisite: **Docker Desktop must be running** - otherwise the
   job skips the Docker steps by design, and a skipped e2e does NOT count as
   validation.
3. **Local stack vs CI.** The local dev stack must not hold the published
   ports (3030/8082/8100/8101/8890/9092/9090/3000) when backend pushes are
   expected: CI fails fast with "port is already allocated" by design (it
   never tears down a local stack). Free the ports with `docker compose stop`
   (containers and volumes are preserved).
4. **Web-only pushes skip e2e.** `ci.yml` carries `paths-ignore: ['web/**']`;
   `.github/workflows/web.yml` runs the unit suite for web-only pushes.
   Mixed pushes run both workflows (the unit suite twice - harmless).
5. **Honesty contract.** An offline-green suite is NOT "done" for backend
   changes: a green CI run with the real e2e is required before
   CHANGELOG/BACKLOG/FEN-SYNC claims. Test counts must be the actual `pytest`
   number (currently 111). Never claim browser-verified or e2e-verified what
   was only unit-tested.
6. **Git hygiene with parallel sessions.** Always `git status -s` before
   committing and before pushing; push only from a clean tree. After any
   change run `pytest -q`, update CHANGELOG/BACKLOG, then refresh
   `C:\FEN-GRAPHIA\FEN-SYNC.md` with `python C:\FEN-GRAPHIA\fen_sync_check.py`.
7. **Roles.**
   - **Owner:** external actions only - GitHub billing fix (hosted runners,
     step 7 revert), NAAN/N2T registration, Vercel Root Directory, ADR-006
     acceptance.
   - **Working chats:** features/bugfixes offline + pytest, commits, pushes,
     CI verification, CHANGELOG/BACKLOG upkeep.
   - **Google Jules bot:** opens PRs - review before merging (its PID-helper
     PR carried unrelated vercel/landing changes and introduced the `/triadic`
     -> `/triadic.html` 404 regression).

Ops notes (learned the hard way):

- **Stale runner session.** If a CI run stays `queued` while the runner API
  reports `busy` with no visible in-progress job, a stale session is stuck
  (typically after the runner service was restarted mid-job). Do NOT restart
  the service again: the listener retries session creation every ~30 s
  (`_diag\Runner_*.log` shows "Session created" when it recovers); then
  cancel the stuck run and re-run it.
- **Runner offline.** While the machine is off or Docker Desktop is updating,
  jobs queue with multi-hour durations. Check
  `gh api repos/riznykst/fen-triadic-synthesis/actions/runners` - expect
  `"status": "online"`.
- **Diagnostics.** Listener log: `C:\actions-runner\_diag\Runner_*.log`;
  job log: `Worker_*.log`. Service control:
  `C:\nssm\nssm-2.24\win64\nssm.exe stop|start GitHubActionsRunner`.
- **CI actions.** `actions/checkout@v5` (v4 targets deprecated Node.js 20);
  the earlier `dorny/paths-filter` was replaced by native `paths-ignore` +
  `web.yml`.

## Incident log

### 2026-09-02 - D: (SD card) failure and full recovery
- The SD card hosting `D:\FEN-GRAPHIA` failed mid-session: files were wiped
  with 0xFF garbage (repo working tree, `.vendor`, `FEN-SYNC.md`,
  `fen_sync_check.py`, the old `actions-runner` install, nssm). The local
  `.git` was destroyed too; only a handful of root files survived.
- No committed work was lost: the GitHub remote was the source of truth.
- Recovery (all on C:, NTFS):
  - Repo: cloned to `C:\fen-triadic-synthesis` (HEAD preserved, 111 tests
    green with the fresh venv `C:\fen-venv`).
  - Runner: reinstalled from scratch at `C:\actions-runner` (v2.337.0),
    registered as `fen-laptop`, NSSM service `GitHubActionsRunner`
    (`C:\nssm\nssm-2.24\win64\nssm.exe`) running `cmd.exe /c run.cmd`, work
    dir `C:\fen-runner-work`. A full service recreate was required: the old
    service ImagePath still pointed at the dead `D:\...\nssm.exe`.
  - The landing-page rewrite (uncommitted at the time) was the only file
    that survived intact on D: and was restored into the clone.
- **Do not write to D: until the card is replaced or reformatted.**
  Convention files (FEN-SYNC.md, fen_sync_check.py) now live at
  `C:\FEN-GRAPHIA\`.
