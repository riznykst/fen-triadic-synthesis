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

## Kafka delivery guarantees

The pipeline is **at-least-once** end to end — messages are never silently
dropped, but a crash between processing and commit can redeliver a message
(downstream steps must be idempotent; the SPARQL update already is, see
`services/validation_consumer/sparql_updater.py`):

- **Producer** (`services/common/kafka_io.py::make_producer`):
  `acks='all'` (the leader acks only once every in-sync replica holds the
  record) + `retries=5` with `enable_idempotence=True` (producer-side retries
  never duplicate a record) + `linger_ms=50` for small batches.
  `send()` attaches delivery callbacks, so broker-side delivery failures
  (`KafkaError`) are logged loudly instead of silently dropped.
- **Consumer** (`make_consumer`): `enable_auto_commit=False` — offsets are
  committed **only after processing** (commit-after-processing).
- **FEN Bridge outbound** (`outbound.py::run`): the batch's offsets are
  committed only when `submit_candidates` returned True; on False they stay
  uncommitted and the batch is redelivered.
- **Validation Result Consumer** (`main.py::process_cycle`): each message's
  offset is committed explicitly (`commit_offsets`, offset+1) only after the
  SPARQL update AND the EntityValidated publication succeeded. A failure is
  logged loudly and the cycle stops without committing, so the failed message
  is redelivered on the next rebalance or restart.

Exactly-once is deliberately out of scope: the DAO decision is a state
update (idempotent SPARQL DELETE/INSERT) and the confirmation event is
re-publishable, so duplicates are harmless by design (ADR-001).

## Kubernetes / OKD deployment

`k8s/` holds Deployment + Service manifests for the three application
services, plus shared config:

| Deployment | Manifest | Exposes |
|---|---|---|
| `fen-bridge-outbound` | `k8s/fen-bridge-outbound.yaml` | no HTTP port (headless Service) |
| `fen-bridge-webhook` | `k8s/fen-bridge-webhook.yaml` | HTTP `:8101` (Service `fen-bridge-webhook`) |
| `validation-consumer` | `k8s/validation-consumer.yaml` | no HTTP port (headless Service) |

Shared environment comes from `k8s/configmap.yaml` (`KAFKA_BOOTSTRAP_SERVERS`,
`TOPIC_*`, `FEN_API_BASE_URL`, `SPARQL_UPDATE_ENDPOINT`, `FEN_NAAN`).
`k8s/secret.yaml` carries `FEN_WEBHOOK_TOKEN` — its value is the base64 of the
empty string (no auth) and **must be replaced with a real secret before any
non-local deployment**, otherwise anyone could forge a DAO decision and
overwrite `gfen:validationStatus` (see `webhook.py`).

Kafka and the RDF store (**Virtuoso** in production, Fuseki in local dev) are
**external** to this deployment — the manifests assume a DAP-managed broker
and a SPARQL endpoint, and never run them. Image tags
(`fen/fen-bridge-*:latest`, `fen/validation-consumer:latest`) are placeholders
replaced by the build pipeline. Apply order: `kubectl apply -f k8s/`.
