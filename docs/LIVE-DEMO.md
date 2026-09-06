# FEN — Live Demo Guide (local stack, real data)

How to run the full FEN stack locally and drive the web UI against **live
data** (candidates, votes, SSE updates, registry records). The Vercel
deployments (`fen-triadic-synthesis.vercel.app`) serve the *static* UI only —
there is no public backend behind them, so live data requires the local
stack described here.

## 1. Prerequisites

- Docker Desktop **running** (the stack is Kafka + Fuseki + 6 FEN services).
- Repo checked out, e.g. `C:\fen-triadic-synthesis` (or your clone).
- A modern browser (Chrome/Edge/Firefox).

## 2. Start the stack (default: auto mode)

```bash
cd fen-triadic-synthesis
docker compose up --build -d
```

Wait until the containers are healthy (first build pulls images; ~1–3 min):

```bash
docker compose ps
# look for: kafka (healthy), mock-fen-api (healthy), fen-bridge-webhook (healthy),
#           fen-bridge-outbound, validation-consumer, status-api, fuseki
```

Optional sanity check of the whole pipeline:

```bash
python scripts/smoke_test.py        # auto mode end-to-end (candidate -> validated)
```

## 3. Open the UI

| View | URL |
|---|---|
| Classic DAO portal | http://localhost:8082/web/portal/ |
| Triadic view (Scaffold → Consensus → Registry) | http://localhost:8082/web/portal/triadic.html |
| Flow-2 status widget demo | http://localhost:8082/web/widget/demo.html |
| Widget embedding example | http://localhost:8082/web/widget/embed-example.html |

> The UI is served by the **status-api** container (`FEN_WEB_DIR=web`); it
> talks to the mock FEN API at `:8100` and its own SPARQL reads at `:8082`.
> No extra configuration is needed when running locally.

## 4. Drive the demo (auto mode)

1. Open the **classic portal** and submit a candidate (any `entity_label`,
   e.g. *"Komi river term 'yu' means water"*).
2. The card appears as `pending`; after the configured delay
   (`MOCK_FEN_DECISION_DELAY_S`, default 3 s) the simulated DAO adopts the
   LLM/rule recommendation and the record flips to `validated` — watch the
   **live update** (SSE), no page refresh needed.
3. In the **triadic view**, run *Scaffolding* on a natural-language
   statement: the agent returns a structured triple + SHACL result +
   matcher/disambiguator agents (LLM optional via `FEN_LLM_*`; rule
   fallback works offline).
4. Export a record from the portal (TTL / JSON-LD / N-Triples / RO-Crate) —
   the Status API serves `/api/v1/export/{id}`.

## 5. Drive community / QV voting (demo modes)

The mock reads `FEN_MOCK_VOTING` **at startup**, so switch modes by
recreating the mock with the voting override file:

```bash
# Community mode (classic count quorum)
FEN_MOCK_VOTING=community FEN_MOCK_QUORUM=2 \
  docker compose -f docker-compose.yml -f docker-compose.voting.yml up -d

# QV mode (weighted scores, threshold 10)
FEN_MOCK_VOTING=qv FEN_MOCK_QV_THRESHOLD=10 \
  docker compose -f docker-compose.yml -f docker-compose.voting.yml up -d
```

Then, in the portal:

1. Submit a candidate — it stays `pending` (no auto decision).
2. Cast votes (`POST /candidates/{id}/vote` from the UI or API):
   - community: each vote counts; quorum = `FEN_MOCK_QUORUM`, majority wins;
   - QV: vote with `intensity` 1–5 (cost = intensity²); an outcome wins when
     its weighted score reaches `FEN_MOCK_QV_THRESHOLD`.
3. QV also supports **delegation** (`POST /candidates/{id}/delegate`) — a
   non-voting voter's weight follows their delegate.
4. When the threshold is reached the record flips to `validated` (or
   `disputed`/`rejected` by majority) and reputation rewards are applied.

> Windows PowerShell note: set env vars inline as above works in bash; in
> PowerShell use `$env:FEN_MOCK_VOTING="qv"` before the `docker compose`
> command, then `docker compose -f docker-compose.yml -f
> docker-compose.voting.yml up -d`.

## 6. Go back to auto mode

```bash
docker compose down                 # full teardown
docker compose up --build -d        # fresh start, auto mode again
```

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| `docker compose ps` shows unhealthy kafka/mock | give it time; `docker compose logs kafka`, `docker compose logs mock-fen-api` |
| Ports already in use (8082/8100/8101/9092/3030) | another stack is running: `docker compose down` first (CI uses the isolated `fen-ci` project name, so CI runs are unaffected) |
| Portal loads but shows "no candidates" | the mock is in `auto` mode and already decided+delivered, or the wrong API base is configured — check the Configuration fields on the page (defaults: `http://localhost:8100`, `http://localhost:8082`) |
| No SSE live updates | some browsers block SSE to plain HTTP from HTTPS pages only — on localhost HTTP it works; hard-refresh the page |
| Want the LLM judge in Scaffolding | set `FEN_LLM_BASE_URL` / `FEN_LLM_API_KEY` / `FEN_LLM_MODEL` (any OpenAI-compatible endpoint); without them the rule fallback is used (offline-safe) |

## 8. What you should be able to show

- Candidate submission → `gfen:pending` → (community/QV quorum) →
  `gfen:validated` with a decision PID (`ark:99999/gNNNNN`), reputation
  snapshot PID and a ledger anchor (`0xMOCK…` until real anchoring, ADR-001).
- Scaffolding with SHACL structural validation and the ADR-004 boundary
  (the agent structures, the DAO decides).
- Registry graph + RDF/RO-Crate export; the embeddable `<fen-status>` widget
  rendering the live status badge.
