# AGENT_PLAN.md — FEN Bridge MVP: build order for an AI coding agent

This is a step-by-step build plan for an autonomous coding agent (Claude Code or
similar). Follow phases in order — each has a Definition of Done (DoD) that must
pass before moving to the next. Do not skip ahead: later phases depend on files
created in earlier ones.

Scope of this MVP: implement the **FEN Bridge** and **Validation Result Consumer**
microservices from the whitepaper (`docs/FEN-Whitepaper-Triadic-Synthesis.pdf`, §4.2), plus a **mock FEN
API** that simulates DAO governance so the whole loop is demonstrable without real
blockchain/DAO infrastructure. Real Virtuoso is *not* required for local dev — use
Apache Jena Fuseki as a SPARQL 1.1-compatible stand-in (same protocol, swap the
endpoint URL for production).

Out of scope for this MVP: real DAO/Quadratic Voting logic, real on-chain
anchoring, ORCID-based identity, production Kafka cluster config, Kubernetes
manifests. These come after the MVP is validated end-to-end.

---

## Phase 0 — Project scaffold

**Files to create:**
```
fen/
├── LICENSE
├── requirements-common.txt
├── services/common/__init__.py
├── services/common/messages.py
├── services/common/gfen_ontology.py
├── services/common/pid.py
```

**Tasks:**
1. Create the package skeleton above (empty `__init__.py` files where needed).
2. `services/common/messages.py` — Pydantic v2 models for the three Kafka message
   types used across the pipeline: `EntityCandidate`, `GovernanceDecision`,
   `EntityValidated`. These are the single source of truth for message shape —
   JSON Schemas in `schemas/kafka-events/` are generated from them, not written
   by hand.
3. `services/common/gfen_ontology.py` — Python constants mirroring
   `docs/ontology/fen-ontology.ttl`: the `gfen:` namespace URI, status/method
   enums, property URIs. Must stay in sync with the `.ttl` file — if you change
   one, change the other in the same commit.
4. `services/common/pid.py` — ARK/w3id PID helpers: `mint_ark(naan, kind, seq)` and
   `w3id_uri(kind, ref)`, matching the scheme in the whitepaper §4.3
   (`ark:{NAAN}/g00042` → `https://w3id.org/fen/id/decision/g00042`).

**DoD:** `python -c "from services.common import messages, gfen_ontology, pid"`
runs with no import errors.

---

## Phase 1 — Message schemas

**Files to create:**
```
scripts/generate_schemas.py
schemas/kafka-events/entity-candidate.schema.json      (generated)
schemas/kafka-events/governance-decision.schema.json   (generated)
schemas/kafka-events/entity-validated.schema.json      (generated)
```

**Tasks:**
1. Write `scripts/generate_schemas.py`: imports the three Pydantic models from
   Phase 0 and dumps `model_json_schema()` for each into
   `schemas/kafka-events/*.schema.json`.
2. Run it once and commit the generated files. Re-run and re-commit whenever a
   model in `messages.py` changes — never hand-edit the generated JSON.

**DoD:** the three `.schema.json` files exist, are valid JSON, and validating a
sample message from `examples/` against them succeeds.

---

## Phase 2 — FEN Bridge (outbound: DAP → FEN)

**Files to create:**
```
services/fen_bridge/__init__.py
services/fen_bridge/config.py
services/fen_bridge/kafka_io.py
services/fen_bridge/outbound.py
services/fen_bridge/fen_client.py
services/fen_bridge/requirements.txt
```

**Tasks:**
1. `config.py` — env-driven settings (Kafka bootstrap servers, source/target
   topics, FEN API base URL, batch size, poll timeout). No hardcoded hosts.
2. `kafka_io.py` — thin consumer/producer wrappers over `kafka-python`, shared by
   both services in this phase and Phase 3.
3. `fen_client.py` — HTTP client posting a batch of `EntityCandidate` to the mock
   FEN API's `POST /candidates`. Must not raise on individual message failure —
   log and continue (matches the "no blocking points" principle, D2.2 §4.1).
4. `outbound.py` — consumer loop: reads `dap.entities.pending_validation.v1`,
   batches, forwards via `fen_client.py`. This is the process that runs as the
   `fen-bridge-outbound` container.

**DoD:** unit tests in `tests/test_fen_bridge.py` (Phase 5) pass using a mocked
Kafka consumer and a mocked HTTP client — no live broker required to validate
logic.

---

## Phase 3 — FEN Bridge (inbound: FEN → DAP webhook)

**Files to create:**
```
services/fen_bridge/webhook.py
```

**Tasks:**
1. `webhook.py` — a small FastAPI app exposing `POST /webhook/decision`. Receives
   a `GovernanceDecision` payload from the (mock or real) FEN system, validates
   it against the Pydantic model, and publishes it to
   `fen.governance.decisions.v1`. This is the process that runs as the
   `fen-bridge-webhook` container.

**DoD:** `TestClient(app).post("/webhook/decision", json=sample_decision)` returns
`202` and the message appears on the mocked producer's send-call arguments.

---

## Phase 4 — Validation Result Consumer

**Files to create:**
```
services/validation_consumer/__init__.py
services/validation_consumer/config.py
services/validation_consumer/sparql_updater.py
services/validation_consumer/main.py
services/validation_consumer/requirements.txt
```

**Tasks:**
1. `sparql_updater.py` — builds and executes the SPARQL `DELETE/INSERT` that
   writes `gfen:validationStatus` and related properties into the correct named
   graph in the RDF store, given a `GovernanceDecision`. Must be a pure function
   returning the SPARQL string, separately testable from the HTTP execution call
   (see Phase 5's rdflib-based test).
2. `main.py` — consumer loop: reads `fen.governance.decisions.v1`, calls
   `sparql_updater`, executes against the configured SPARQL Update endpoint,
   then publishes an `EntityValidated` confirmation to
   `dap.entities.validated.v1`.

**DoD:** `tests/test_sparql_updater.py` passes by applying the generated SPARQL
string to an in-memory `rdflib.Graph` and asserting the resulting triples match
expectations — this validates correctness without needing Fuseki or Virtuoso
running.

---

## Phase 5 — Tests

**Files to create:**
```
tests/__init__.py
tests/test_pid.py
tests/test_messages.py
tests/test_fen_bridge.py
tests/test_sparql_updater.py
```

**Tasks:** write the tests described in Phases 0–4's DoD sections. All tests must
run offline (no live Kafka, no live SPARQL endpoint, no network calls) — use
`unittest.mock` for Kafka and HTTP, and `rdflib.Graph` in-memory for SPARQL.

**DoD:** `pytest -q` passes with zero failures and zero network access.

---

## Phase 6 — Mock FEN API (demo DAO)

**Files to create:**
```
mock_fen_api/__init__.py
mock_fen_api/main.py
mock_fen_api/requirements.txt
```

**Tasks:**
1. `main.py` — FastAPI app with `POST /candidates` (accepts a batch, schedules a
   background task) and, after a configurable delay, calls back
   `fen-bridge-webhook`'s `/webhook/decision` with a synthetic `GovernanceDecision`
   (random or rule-based outcome). This stands in for real DAO/Quadratic Voting
   for demo purposes only — clearly commented as such, never to be mistaken for
   production governance logic.

**DoD:** running `uvicorn mock_fen_api.main:app` and posting a sample candidate
results in a webhook callback within the configured delay, observable in logs.

---

## Phase 7 — Local orchestration

**Files to create:**
```
docker-compose.yml
.env.example
```

**Tasks:**
1. `docker-compose.yml` — services: `zookeeper`, `kafka`, `fuseki` (local-dev
   stand-in for Virtuoso — comment this clearly), `mock-fen-api`,
   `fen-bridge-outbound`, `fen-bridge-webhook`, `validation-consumer`.
2. `.env.example` — every variable from each service's `config.py`, with safe
   local-dev defaults.

**DoD:** `docker compose up` brings up all seven services with no crash-loops
(check via `docker compose ps` — all `Up`).

---

## Phase 8 — End-to-end smoke test

**Tasks:**
1. Publish one `EntityCandidate` message onto `dap.entities.pending_validation.v1`
   manually (e.g. via `kafka-console-producer` or a small script).
2. Confirm, within the mock FEN API's configured delay, that:
   - `fen.governance.decisions.v1` receives a `GovernanceDecision`;
   - the named graph in Fuseki now contains `gfen:validationStatus
     gfen:validated` (or `gfen:rejected`) for that entity;
   - `dap.entities.validated.v1` receives the corresponding `EntityValidated`
     confirmation.

**DoD:** the full loop completes without manual intervention beyond the initial
publish. This is the artefact to demonstrate to the consortium (whitepaper §8,
"MVP" bullet).

---

## Guardrails for the agent (apply throughout, all phases)

- Never write directly to `triple:*` classes or modify anything under a
  `graphia/` or `gotriple/` path — this repo only ever touches the additive
  `gfen:` namespace (ADR-002).
- Never implement real on-chain writes in this MVP — `gfen:ledgerAnchor` may be
  a stubbed string in the mock, but no wallet/contract code belongs in this
  repository until ADR-001's scope is formally extended.
- Every new Kafka message field must be added to `services/common/messages.py`
  first, then propagated to schemas (Phase 1) and consumers — never the reverse.
- Keep `fen_bridge` and `validation_consumer` fully independent processes/images.
  Neither may import from the other.
