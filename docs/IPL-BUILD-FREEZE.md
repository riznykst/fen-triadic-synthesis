# FEN — IPL 2026 Build Freeze Specification

**Target Event:** GRAPHIA × LUMEN Innovation Prototyping Lab 2026 (14–18 September 2026)
**Target Status:** «Research Prototype v0.1 — Build Freeze»
**Effective Date:** May 2026

---

## Build Freeze Statement

This document defines the strict scope freeze for the **Federated Epistemic Node (FEN)** research prototype for the IPL 2026 demonstration. No new features, external integrations, or architectural refactorings will be added beyond this frozen state.

---

## 1. Included Capabilities (Stable for IPL)

- **Agentic Scaffolding (Phase 1):** OpenAI-compatible LLM provider adapter (`services/common/llm.py`) with deterministic rule fallback, running SHACL shape validation (`docs/ontology/fen-shapes.ttl`).
- **Decentralized Validation & Governance (Phase 2):** Pure Quadratic Voting math ($Cost = Intensity^2$), quorum threshold calculations, and liquid democracy vote delegation (`mock_fen_api/`).
- **Immutable Integration & Provenance (Phase 3):** SPARQL 1.1 Update generator (`services/validation_consumer/sparql_updater.py`), ARK / w3id PID scheme formatting (`services/common/pid.py`), and on-chain ledger transaction hash anchoring (`gfen:ledgerAnchor`).
- **Federation Infrastructure:** Outbound Kafka consumer, inbound FastAPI webhook, read-only SPARQL Status API, and zero-build web portal (`web/portal/triadic.html`) with live SSE updates and embeddable status badge widget (`web/widget/`).
- **Testing & Verification:** 111 passing unit/integration tests, SHACL shape check script (`scripts/shacl_check.py`), and JSON Schema validator (`scripts/generate_schemas.py --check`).

---

## 2. Intentionally Deferred Items

- **Production Smart Contracts:** Real EVM / Solana / Cosmos on-chain voting smart contracts are replaced by local hash notarization and mock webhook callbacks.
- **Sybil Resistance Protocols:** Gitcoin Passport / BrightID / Staking mechanisms are documented in ADR-005 but deferred from local prototype code.
- **Production NAAN Registration:** Official Name Assigning Authority Number (NAAN) registration with N2T is deferred; prototype uses dev NAAN `99999`.
- **ADR-006 Tokenless Challenge Window:** Remains a draft specification for post-IPL development.

---

## 3. Known Limitations

- **Local Mock Governance:** `mock_fen_api` simulates a DAO quorum locally and is not intended for production multi-tenant deployment.
- **In-Memory Triples in Unit Tests:** Offline tests use RDFLib in-memory datasets (`Dataset`/`Graph`) rather than live Virtuoso servers.
- **Sandbox Environment Docker Restriction:** Docker-in-Docker layer extraction (`overlayfs`) is restricted in constrained AI sandboxes; execution against live Docker daemon requires standard Linux/macOS host (verified in CI).

---

## 4. Not Implemented (External Dependencies)

- **Live GRAPHIA DAP Connection:** Direct network connection to GRAPHIA's live Kafka event bus or production Virtuoso cluster.
- **GRAPHIA Production Authentication:** OAuth2 / Keycloak integration with GRAPHIA portal users.

---

## 5. Canonical Demo Path

The single canonical 3-minute demonstration path for IPL evaluators is documented in [`docs/IPL-DEMO.md`](IPL-DEMO.md):
```text
Human contribution → Agentic scaffolding → Structured claim → Community review → Governance decision → Provenance → RDF registry
```

---

## 6. Non-Negotiable Architectural Invariants

1. **`LLM ≠ Governance Authority` ([ADR-004](adr/ADR-004-llm-judge-decision-support-only.md)):**
   The LLM assists in structuring claims and offering suggestions, but **never votes, never determines governance outcomes, and never writes `gfen:validationStatus`**.
2. **Epistemic Authority Remains with Communities:**
   The community DAO retains sole authority to validate, dispute, or reject linguistic knowledge claims.
3. **FEN as Non-Invasive Federation Overlay ([ADR-002](adr/ADR-002-federation-node-not-embedded.md)):**
   FEN does not modify or replace GRAPHIA/GoTriple core infrastructure; it operates via standard external interfaces (Kafka, SPARQL Updates on named graphs, REST).
4. **GDPR Right-to-Erasure via Content-Free Anchoring ([ADR-001](adr/ADR-001-rdf-anchoring-not-full-onchain.md)):**
   Only cryptographic hashes of decisions are anchored on-chain. All textual content stays in Virtuoso stores.
