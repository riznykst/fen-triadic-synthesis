# FEN × GRAPHIA Integration Specifications

**Target Architecture:** GRAPHIA Data Acquisition Platform (DAP) & GoTriple Knowledge Graph
**Integration Strategy:** Autonomous External Federation Overlay Node ([ADR-002](adr/ADR-002-federation-node-not-embedded.md))
**Document Status:** integration specification for the IPL 2026 demo preparation

---

## Technical Integration Overview

FEN (Federated Epistemic Node) connects to GRAPHIA without modifying core GRAPHIA DAP microservices, indexing engines, or Virtuoso knowledge graph infrastructure. Integration occurs purely via the Kafka event bus, SPARQL 1.1 Update queries on designated named graphs, and REST Status APIs.

```text
[ GRAPHIA DAP Pipeline ]
     │  emits candidates (dap.entities.pending_validation.v1)
     ▼
[ FEN Bridge (Outbound) ]  ──────>  [ Agentic Scaffolding & Community DAO ]
                                                    │
[ Validation Result Consumer ]  <──  [ FEN Bridge (Webhook Callback) ]
     │  applies SPARQL update
     ▼
[ Virtuoso (GoTriple KG) ]  ──────>  [ Status API / <fen-status> Widget ]
```

---

## Integration Status Categorization

### 1. IMPLEMENTED (Genuinely Exists & Tested in Repository)

- **`gfen:` RDF Ontology Extension:** Defined in `docs/ontology/fen-ontology.ttl`. Extends GRAPHIA/TRIPLE provenance (`oa:Annotation`, named graphs) without modifying core classes.
- **SHACL Shape Validation:** SHACL shapes in `docs/ontology/fen-shapes.ttl` validated via `pyshacl` (`scripts/shacl_check.py`).
- **Kafka IO Consumer & Producer Wrappers:** At-least-once delivery semantics (`acks=all`, idempotent producer) in `services/common/kafka_io.py`.
- **SPARQL 1.1 Update Builder:** `services/validation_consumer/sparql_updater.py` constructs idempotent `INSERT/DELETE` queries tested against OpenLink Virtuoso syntax.
- **Webhook Callback Handler:** `services/fen_bridge/webhook.py` enforces Bearer-token auth (`FEN_WEBHOOK_TOKEN`) and republishes decisions to Kafka.
- **Read-Only Status API:** `services/status_api/main.py` provides REST endpoints and exports RDF (Turtle, JSON-LD, N-Triples) and RO-Crate metadata.
- **Embeddable Status Widget:** Zero-build `<fen-status>` Web Component (`web/widget/`) resolving entity validation badges live via the Status API.

---

### 2. INTERFACE-READY (Defined Technical Boundaries, Ready for Broker/Endpoint Wiring)

- **Kafka Topic Schemas:** JSON Schemas generated from Pydantic models (`schemas/kafka-events/`):
  - `dap.entities.pending_validation.v1` (`EntityCandidate`)
  - `fen.governance.decisions.v1` (`GovernanceDecision`)
  - `dap.entities.validated.v1` (`EntityValidated`)
- **Named Graph URI Pattern:** Bounded to `urn:graphia:document:{id}:graph` or custom configurable URI templates (`SPARQL_GRAPH_TEMPLATE`).
- **OpenAI-Compatible LLM Adapter:** `services/common/llm.py` accepts any standard endpoint, allowing pluggable connection to GRAPHIA's LLM services (LLM4SSH / Quagga) if exposed via an OpenAI-compatible interface.

---

### 3. PROPOSED (Architectural Design / Whitepaper Proposals)

- **Consortium NAAN Allocation:** Formal registration of an official Name Assigning Authority Number (NAAN) with N2T for ARK PIDs (`ark:{FEN_NAAN}/g#####`).
- **Production Quadratic Voting Smart Contracts:** On-chain voting contract deployment on Ethereum L2 / POSI-compliant DLT networks.
- **Sybil-Resistant Identity Federation:** Integration with academic/consortium SAML/eduGAIN or Decentralized Identity (DID) providers.

---

### 4. NOT IMPLEMENTED (Future Expansion Beyond Prototype Scope)

- **Live Production Connections:** No live network connections or credentials for GRAPHIA production Kafka brokers or production Virtuoso endpoints are configured in this repository.
- **Automatic Graph Rollback on Dispute:** Disputes mark `gfen:disputed` in the named graph; automatic removal of base entities is intentionally omitted to preserve data integrity.

---

## Technical Contract Summary

| Contract | Local Prototype | GRAPHIA Production Target |
|---|---|---|
| **Event Bus** | Apache Kafka (docker-compose) | GRAPHIA DAP Kafka Event Bus |
| **KG Triple Store** | Apache Jena Fuseki / Local Virtuoso | GRAPHIA GoTriple Virtuoso Cluster |
| **SPARQL Endpoint** | `http://fuseki:3030/ds/update` | GRAPHIA DAP SPARQL Update Endpoint |
| **PID Resolver** | Mock NAAN `99999` | Registered Consortium NAAN via N2T / w3id.org |
| **LLM Backend** | Local Mock / DeepSeek / OpenAI | LLM4SSH / Quagga HPC Endpoint |
