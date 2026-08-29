# Self-hosted GitHub Actions runner (billing-block workaround)

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
| Runner dir | `D:\FEN-GRAPHIA\actions-runner` (outside the repo) |
| Work dir | `C:\fen-runner-work` — D: is full and does not support symlinks |
| Git fix | `.env` → `GIT_CONFIG_GLOBAL` pointing to a config with `safe.directory = *` (D: is FAT; git sees every directory as "dubious ownership") |
| Python | system `C:\Python310` (actions/setup-python toolchains get wiped by this environment; matrix reduced to 3.10 — TEMPORARY) |
| Shell for docker check | `powershell` (System32): `bash` resolves to WSL bash (breaks Windows paths), `pwsh` is not in the runner PATH |

Service management:

```powershell
D:\FEN-GRAPHIA\nssm\nssm-2.24\win64\nssm.exe stop GitHubActionsRunner
D:\FEN-GRAPHIA\nssm\nssm-2.24\win64\nssm.exe start GitHubActionsRunner
D:\FEN-GRAPHIA\nssm\nssm-2.24\win64\nssm.exe remove GitHubActionsRunner confirm
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
