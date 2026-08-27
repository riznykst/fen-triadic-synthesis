# Architecture

Full rationale lives in [`whitepaper.docx`](whitepaper.docx) and the three ADRs in
[`adr/`](adr/). This document is the quick-reference version: what talks to what,
and where each piece lives in the repo.

## Data flow

```
doc.normalized.v1
     │
     ▼
[ Entity & Relation Extraction ]     existing GRAPHIA WP4 service — untouched
     │  emits candidates, status = pending
     ▼
dap.entities.pending_validation.v1
     │
     ▼
[ FEN Bridge — outbound ]            services/fen_bridge/outbound.py
     │  forwards batches via HTTP
     ▼
   [ mock_fen_api/ ]  (demo only)  ←→  [ real Agentic Scaffolding + DAO ]  (production)
     │  webhook callback, async
     ▼
[ FEN Bridge — webhook ]             services/fen_bridge/webhook.py
     │  validates + republishes
     ▼
fen.governance.decisions.v1
     │
     ▼
[ Validation Result Consumer ]       services/validation_consumer/main.py
     │  SPARQL UPDATE into named graph (services/validation_consumer/sparql_updater.py)
     ▼
dap.entities.validated.v1  →  Publisher (unchanged)  →  Virtuoso (GoTriple KG)
```

## Component map

| Component | File(s) | Runs as |
|---|---|---|
| Shared message contracts | `services/common/messages.py` | imported by all Python services |
| `gfen:` ontology constants | `services/common/gfen_ontology.py` | imported by all Python services |
| PID helpers (ARK/w3id, ADR-003) | `services/common/pid.py` | imported by `sparql_updater.py` |
| Kafka IO wrappers | `services/common/kafka_io.py` | imported by the two consumer processes |
| FEN Bridge (outbound) | `services/fen_bridge/outbound.py`, `fen_client.py` | `fen-bridge-outbound` container |
| FEN Bridge (webhook) | `services/fen_bridge/webhook.py` | `fen-bridge-webhook` container |
| Validation Result Consumer | `services/validation_consumer/main.py`, `sparql_updater.py` | `validation-consumer` container |
| Mock DAO (demo only) | `mock_fen_api/main.py` | `mock-fen-api` container |
| RDF store (local dev) | — | `fuseki` container, stand-in for Virtuoso (see ADR-001) |
| Message bus | — | `kafka` + `zookeeper` containers |

Two new DAP-side microservices exist: the **FEN Bridge** (two independent
processes: outbound + webhook) and the **Validation Result Consumer**. Of these,
only the FEN Bridge talks to the external FEN system — everything else in the
governance stack lives outside GRAPHIA (ADR-002).

## Two boundaries that must never move

1. **Content vs. governance metadata** (ADR-001) — linguistic content stays in
   Virtuoso; only a decision hash is ever anchored on-chain. Enforced in code by
   `gfen:ledgerAnchor` being the *only* field in `sparql_updater.py` sourced from
   `decision.ledger_anchor`, never from raw entity content.
2. **FEN vs. GRAPHIA core** (ADR-002) — the only files that touch anything
   GRAPHIA-owned are `services/fen_bridge/` (talks to Kafka topics that already
   exist in the DAP) and `docs/ontology/fen-ontology.ttl` (an additive namespace).
   Nothing in this repo imports from, or writes to, `triple:*` classes.

## PIDs (ADR-003)

Governance records are dereferenceable via `ark:{FEN_NAAN}/{g|v|r|s}NNNNN`
→ `https://w3id.org/fen/id/{decision|validation|reputation-snapshot|session}/...`.
In the named graph, `gfen:governanceDecisionId` and `gfen:reputationSnapshot`
are IRIs (not literals); `gfen:ledgerAnchor` is the only literal tx reference.
See [`adr/ADR-003-fen-pid-scheme.md`](adr/ADR-003-fen-pid-scheme.md).

## Local dev vs. production

| | Local dev (this repo, `docker-compose.yml`) | Production |
|---|---|---|
| RDF store | Apache Jena Fuseki | Virtuoso (GRAPHIA's authoritative store) |
| DAO / governance | `mock_fen_api/` (random/rule-based outcome) | Real Agentic Scaffolding + Quadratic Voting DAO |
| On-chain anchor | Stubbed string (`0xMOCK...`) | Real transaction hash |
| Kafka | Single-broker `docker-compose.yml` | GRAPHIA's production Kafka cluster (PCSS) |
| PID NAAN | `FEN_NAAN=99999` (local dev) | FEN's registered NAAN (consortium, whitepaper §7) |

Swapping any row on the right only requires changing environment variables
(`SPARQL_UPDATE_ENDPOINT`, `FEN_API_BASE_URL`, `KAFKA_BOOTSTRAP_SERVERS`,
`FEN_NAAN`) — no application code changes.
