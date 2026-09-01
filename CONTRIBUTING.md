# Contributing

Thanks for your interest in FEN! This is a **research prototype** — the most
valuable contributions are those that sharpen the research artifact, not the
feature surface.

## Ground rules

- **Stay inside the roadmap.** New features must not contradict the
  whitepaper or ADRs 001–006 (see `docs/adr/`). If a proposal does, it needs
  an ADR update first — that is the discussion, not the code.
- **Frontend and backend land in separate commits.**
- **Keep the honesty contract:** README/CHANGELOG/BACKLOG must reflect the
  actual repo state (test counts, CI status, what is real vs. mock). Never
  claim something is verified that is not.
- Run the full suite before pushing: `pytest -q` (104 tests, all offline).

## Getting started

```bash
pip install -r requirements-common.txt
pytest -q                          # unit tests (no Docker needed)
docker compose up --build          # full local stack
python scripts/smoke_test.py       # e2e smoke test
```

Optional: `docker compose --profile virtuoso up -d virtuoso` +
`python scripts/virtuoso_dialect_check.py` to verify SPARQL dialect
compatibility.

## Repository map (30-second tour)

| Path | What it is |
|---|---|
| `services/fen_bridge/` | outbound consumer + inbound webhook (Kafka) |
| `services/validation_consumer/` | SPARQL Update logic + Kafka consumer |
| `services/status_api/` | read-side web service (SPARQL → JSON + RDF export) + static UI |
| `mock_fen_api/` | demo DAO stand-in — **NOT** production governance: `qv_voting.py` (pure QV math), `delegation.py`, `scaffold.py`, `main.py` (routes/state) |
| `services/common/` | shared contracts, PID helpers, Kafka IO, metrics, logging |
| `docs/adr/` | architecture decision records (read before changing behavior) |
| `web/` | zero-build web interface (portal + widget) |
| `tests/` | 104 offline tests |

## How to contribute

1. Fork the repository and create a branch from `main`.
2. Make your change with a clear commit message referencing the relevant
   ADR/BACKLOG item.
3. Add or update tests (offline, mocked Kafka/HTTP/LLM/SPARQL).
4. Run `pytest -q` and, if the change touches the pipeline,
   `python scripts/smoke_test.py` against the Docker stack.
5. Open a pull request. Note: CI currently runs on a self-hosted runner
   (push-triggered only, see `docs/self-hosted-runner.md`) — maintainers
   will run the e2e checks on push.

## Style

- Python 3.10+ typing, `from __future__ import annotations`.
- No Node toolchain for the web layer (zero-build plain HTML/JS).
- Keep modules small and single-purpose (see `mock_fen_api/` layout).

## Code of conduct

Be respectful and constructive. This project is about community-governed
knowledge — the repository should model the governance it studies.