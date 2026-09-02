# FEN — Triadic Synthesis Framework

**A research prototype and reference architecture for a federated epistemic validation layer for community-governed linguistic knowledge** — designed to integrate with the [GRAPHIA](https://graphia-ssh.eu/) SSH Knowledge Graph as an autonomous federation node.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-IPL--Ready%20v0.1-green.svg)](#status)
[![GRAPHIA](https://img.shields.io/badge/integrates%20with-GRAPHIA%20D2.2-informational.svg)](docs/FEN-Whitepaper-Triadic-Synthesis.pdf)
[![Tests](https://img.shields.io/badge/tests-111%20passing-brightgreen.svg)](#status)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](#running-locally)

> **Status: Research Prototype v0.1 — IPL-ready (GRAPHIA × LUMEN Innovation Prototyping Lab 2026).**
> *Runnable locally via `docker compose up`; live GRAPHIA production integration pending.*

---

## Research entry point

**Research question:** *How can AI-assisted knowledge synthesis remain
community-governed without transferring epistemic authority to the AI system?*

**Core idea:**

> **AI scaffolds. Community decides. The knowledge graph records.**

This repository is the runnable companion implementation of:

> Riznyk, V. (2026). *Decentralised Agentic Governance: A Methodology for
> Community-Owned Linguistic Datasets and Knowledge Synthesis* (submitted for
> journal publication; DOI pending — will be linked here and in
> [`CITATION.cff`](CITATION.cff) once active).

**The architecture answers the question with a hard boundary** — the same
boundary the paper argues for (epistemic assistance ≠ epistemic authority):

```text
        AI                     Community                 Knowledge Graph
        │                      │                         │
        ▼                      ▼                         ▼
   SCAFFOLD            →   CONSENSUS            →    REGISTRY
   AI-assisted              community judgment        RDF / provenance
   epistemic                governance (QV,           persistent record
   structuring              reputation, delegation)   (gfen:, PID, anchor)
```

AI participates in structuring. The community retains judgment. The
knowledge graph keeps institutional memory. The ledger anchors integrity —
nothing more ([ADR-001](docs/adr/ADR-001-rdf-anchoring-not-full-onchain.md)).

### Research lineage

```text
PAPER         Decentralised Agentic Governance (2026, DOI pending)
   │
   ▼
FRAMEWORK     Triadic Synthesis — Scaffold → Consensus → Registry
   │
   ▼
SYSTEM        Federated Epistemic Node (FEN)
   │
   ▼
IMPLEMENTATION  Kafka + RDF + mock DAO + PID + Web UI (this repository)
   │
   ▼
EVALUATION    GRAPHIA integration + community validation study (next phase)
```

---

## What this is

WP4 of the GRAPHIA project extracts entities and relations from full-text SSH documents automatically, via AI/NLP services, and commits them directly into the GoTriple Knowledge Graph — with no step for human review, cultural verification, or contributor attribution. That's fine for well-resourced content. It systematically underserves low-resource languages, minority dialects, and culturally specific material.

FEN (Federated Epistemic Node) closes that gap with a three-phase pipeline:

1. **Agentic Scaffolding** — an AI agent guides contributors in structuring linguistic knowledge, without ever deciding on their behalf (a separate FEN-side project, external to this repository — ADR-002).
2. **Decentralised Validation** — a DAO, using Quadratic Voting and reputation-weighted review, decides whether a candidate entity is accepted, disputed, or rejected. The community remains the final arbiter of meaning.
3. **Immutable Integration** — the governance decision is anchored (hash only) on-chain and exposed as a dereferenceable PID ([ADR-003](docs/adr/ADR-003-fen-pid-scheme.md)), while the underlying content stays in GRAPHIA's authoritative RDF store.

**FEN does not replace or modify any part of GRAPHIA's core infrastructure.** It connects as an external federation node — the same architectural pattern GRAPHIA already uses for OpenCitations, EHRI, GESIS, and ORKG (D2.2, §2.1) — and touches the DAP only through two new, non-blocking microservices (the FEN Bridge and the Validation Result Consumer) on the existing Kafka event bus, plus a read-only Status API for the web layer ([ADR-002](docs/adr/ADR-002-federation-node-not-embedded.md)).

## Why it matters

> Current industrial paradigms largely treat language as a raw resource, harvested at scale with limited regard for cultural context or community agency.

This project is the applied counterpart to the academic paper *"Decentralised Agentic Governance: A Methodology for Community-Owned Linguistic Datasets and Knowledge Synthesis"* (Riznyk, 2026), which is submitted separately for journal publication and is not included in this repository. The consortium-facing [`docs/FEN-Whitepaper-Triadic-Synthesis.pdf`](docs/FEN-Whitepaper-Triadic-Synthesis.pdf) summarises that framework specifically for the GRAPHIA integration proposal — read it first if you're evaluating this repo on behalf of the consortium.

## User stories

Two typical use cases — a community contributor of a low-resource-language
entity and a general dataset owner — are described in
[`docs/user-stories.md`](docs/user-stories.md).

## Architecture at a glance

```
doc.normalized.v1
     │
     ▼
[ Entity & Relation Extraction ]     (existing GRAPHIA WP4 service)
     │  emits candidates, status = pending
     ▼
dap.entities.pending_validation.v1
     │
     ▼
[ FEN Bridge — outbound ]            (new DAP microservice — this repo)
     │  forwards batches to the FEN API
     ▼
   [ Agentic Scaffolding → DAO / Quadratic Voting ]
     │  governance decision, asynchronous callback
     ▼
[ FEN Bridge — webhook ]             (validates + republishes to Kafka)
     │
     ▼
fen.governance.decisions.v1
     │
     ▼
[ Validation Result Consumer ]       (new DAP microservice — this repo)
     │  updates gfen:validationStatus in the named graph
     ▼
dap.entities.validated.v1  →  Publisher (unchanged)  →  Virtuoso (GoTriple KG)
```

Candidates are published immediately with `gfen:pending` — the pipeline never blocks on a vote. See the [whitepaper](docs/FEN-Whitepaper-Triadic-Synthesis.pdf), §4, for the full flow and the [architecture doc](docs/architecture.md) for details.

## Running locally

```bash

cp .env.example .env          # optional — docker-compose.yml has working in-container defaults
docker compose up --build
```

This starts Kafka, a Fuseki instance (SPARQL 1.1 stand-in for Virtuoso — see
`docker-compose.yml`'s comment), the mock DAO, and all FEN Bridge/consumer
processes. Once the stack is up, run the end-to-end smoke test
(`scripts/smoke_test.py`, also wired up as the CI `e2e` job): it publishes one
`EntityCandidate` (see `schemas/kafka-events/entity-candidate.schema.json` for
the shape) onto `dap.entities.pending_validation.v1`, waits for the governance
decision, checks the named graph, and verifies the `dap.entities.validated.v1`
confirmation:

```bash
docker compose up --build
# in a second terminal:
python scripts/smoke_test.py
```

Observability: Prometheus on http://localhost:9090 and Grafana on
http://localhost:3000 (dashboard "FEN — Validation Pipeline Overview",
anonymous access) — `docker compose up` starts both.

Optional: verify SPARQL dialect compatibility against a real Virtuoso
(GoTriple KG's engine) before touching GRAPHIA's instance:

```bash
docker compose --profile virtuoso up -d virtuoso
python scripts/virtuoso_dialect_check.py   # PASSED == dialect + idempotency OK
```

> **CI blocked by GitHub billing?** If Actions jobs fail with *"recent account
> payments have failed or your spending limit needs to be increased"*, use a
> self-hosted runner — see [`docs/self-hosted-runner.md`](docs/self-hosted-runner.md).

To run the test suite without Docker (no live Kafka or SPARQL endpoint needed —
everything is mocked or in-memory):

```bash
pip install -r requirements-common.txt
python scripts/generate_schemas.py   # only needed after changing services/common/messages.py
pytest -q
```

## Repository layout

```
fen-triadic-synthesis/
├── README.md                       ← you are here
├── CHANGELOG.md                     dated record of notable changes
├── CITATION.cff                     machine-readable citation metadata (research artifact)
├── SECURITY.md                      vulnerability reporting + current security posture
├── CONTRIBUTING.md                  how to contribute (roadmap + honesty contract)
├── AGENT_PLAN.md                    step-by-step build plan for an AI coding agent
├── LICENSE                          Apache 2.0
├── docker-compose.yml                full local dev stack (Kafka, Fuseki, all services; optional Virtuoso profile)
├── .env.example                      every configurable env var, with local-dev defaults
├── requirements-common.txt           combined deps for running tests locally
├── .github/
│   └── workflows/ci.yml              CI: unit tests + docker-compose e2e on the self-hosted runner (matrix temporarily 3.10; full 3.10–3.12 after the GitHub billing issue is resolved)
├── docs/
│   ├── FEN-Whitepaper-Triadic-Synthesis.pdf   consortium-facing integration proposal
│   ├── architecture.md               quick-reference diagrams + component map
│   ├── adr/
│   │   ├── ADR-001-rdf-anchoring-not-full-onchain.md
│   │   ├── ADR-002-federation-node-not-embedded.md
│   │   ├── ADR-003-fen-pid-scheme.md
│   │   ├── ADR-004-llm-judge-decision-support-only.md
│   │   ├── ADR-005-participation-model-and-dao-threshold.md
│   │   └── ADR-006-tokenless-challenge-window.md (draft)
│   ├── user-stories.md               two typical use cases for the validation layer
│   ├── self-hosted-runner.md        CI workaround while GitHub billing blocks Actions
│   ├── applicability-and-limits.md  where the validation layer fits and where it does not
│   ├── integration-verification-plan.md  how to prove real GRAPHIA + NAAN integration
│   ├── BACKLOG.md                    feature roadmap (Top-10 recommendations + status)
│   ├── images/
│   │   ├── story1-validation-flow.svg     user-story infographic (community validation flow)
│   │   ├── story2-validation-overlay.svg  user-story infographic (validation overlay)
│   │   └── widget-overview.svg          Flow 2 widget data-flow infographic
│   ├── ontology/
│   │   ├── fen-ontology.ttl          the gfen: namespace
│   │   └── fen-shapes.ttl            SHACL shapes for gfen: (ADR-001/003)
│   └── research/
│       └── graphia-tech-stack-2026-08.pdf   GRAPHIA tech-stack research (source for the audit)
├── schemas/
│   └── kafka-events/                 JSON Schemas, generated from services/common/messages.py
│       ├── entity-candidate.schema.json
│       ├── governance-decision.schema.json
│       └── entity-validated.schema.json
├── scripts/
│   ├── generate_schemas.py           regenerates the schemas above — never hand-edit them
│   ├── smoke_test.py                 e2e smoke test — auto + community/QV voting modes (CI `e2e` job)
│   └── virtuoso_dialect_check.py     SPARQL dialect/idempotency check against a real Virtuoso (CI `e2e` job)
├── services/
│   ├── common/                       shared models, gfen: constants, PID helpers, Kafka IO (at-least-once),
│   │                                JSON logging (`logging_config.py`), Prometheus metrics (`metrics.py`)
│   ├── fen_bridge/                   outbound consumer + inbound webhook (2 containers)
│   ├── validation_consumer/          SPARQL Update logic + Kafka consumer
│   └── status_api/                   read-side web service (SPARQL → JSON + RDF/RO-Crate export) + static UI
├── mock_fen_api/                     demo DAO stand-in — NOT production governance
├── web/                              zero-build web interface layer
│   ├── widget/                       Flow 2: embeddable <fen-status> Web Component + demo
│   ├── portal/                       Flow 1: community DAO portal (candidates, voting, triadic view, delegation, SSE live updates)
│   └── api.md                        REST contract (shared with the real FEN backend)
├── k8s/                              Kubernetes/OKD manifests: 4 Deployments + ConfigMap + Secret
monitoring/                        Prometheus scrape config + Grafana provisioning (fen-overview dashboard)
├── tests/                            111 tests, all offline (mocked Kafka/HTTP/LLM/SPARQL, in-memory RDF)
└── examples/
    ├── sample-validation-flow.trig   RDF before/after a validation cycle (TriG, parser-checked)
    └── pid-redirects.tsv             N2T → w3id redirect configuration (ADR-003)
```

Everything under `services/`, `mock_fen_api/`, `tests/`, and `scripts/` is implemented and
tested — see [`AGENT_PLAN.md`](AGENT_PLAN.md) for the phase-by-phase build log and
`docker-compose.yml` to run it end to end.

## Key design decisions

| ADR | Decision |
|---|---|
| [ADR-001](docs/adr/ADR-001-rdf-anchoring-not-full-onchain.md) | Blockchain anchors only a hash of each governance decision. All content stays in GRAPHIA's Virtuoso store — no conflict with ADR002, no GDPR right-to-erasure issue. |
| [ADR-002](docs/adr/ADR-002-federation-node-not-embedded.md) | FEN integrates as an autonomous federation node, not as a component embedded in GoTriple KG or the DAP core. No GRAPHIA partner needs to operate or govern DAO infrastructure. |
| [ADR-003](docs/adr/ADR-003-fen-pid-scheme.md) | Governance records get ARK + w3id.org PIDs under FEN's own NAAN (`g` decision / `v` validation record / `r` reputation snapshot / `s` scaffolding session). A PID is never bound to a blockchain explorer; the tx hash is only the `gfen:ledgerAnchor` attribute. |
| [ADR-004](docs/adr/ADR-004-llm-judge-decision-support-only.md) | The LLM judge is decision-support only — it recommends, the community DAO decides. The LLM never votes and never writes `gfen:validationStatus`; within this repo it is used only by the demo mock. |
| [ADR-005](docs/adr/ADR-005-participation-model-and-dao-threshold.md) | No token economy in the MVP: intrinsic + attribution incentives, near-zero friction (batch voting, delegation), portable reputation. DAO mode from ~20 active validators; below that `gfen:PeerReview`. Motivation = reputation capital + intrinsic; gamification is optional UX only, never a governance input. |
| [ADR-006](docs/adr/ADR-006-tokenless-challenge-window.md) *(draft)* | Optional tokenless challenge window: reputation-lock based disputes (no staking — ADR-005 stays intact); default off, bounded finality delay. |

## The `gfen:` ontology extension

A single additive namespace on top of the existing TRIPLE Ontology provenance model (`oa:Annotation`, named graphs) — no core class is modified:

```turtle
@prefix gfen: <https://w3id.org/got/fen/ontology#> .

gfen:validationStatus      a rdf:Property .  # -> pending | validated | disputed | rejected
gfen:validationMethod      a rdf:Property .  # -> QuadraticVoting | PeerReview
gfen:governanceDecisionId  a rdf:Property .  # -> dereferenceable PID (ark:{FEN_NAAN}/g#####)
gfen:reputationSnapshot    a rdf:Property .  # -> dereferenceable PID (ark:{FEN_NAAN}/r#####)
gfen:ledgerAnchor          a rdf:Property .  # on-chain tx hash, anchor only
gfen:contributorProfile    a rdf:Property .  # -> triple:Profile (reused, not duplicated)
```

The namespace declares `owl:imports` to the GRAPHIA/TRIPLE Ontology — currently
a **stub IRI** (`https://w3id.org/gotriple/ontology`), to be replaced with the
official GRAPHIA Ontology IRI once confirmed with the consortium (whitepaper §7).
The import is declarative only: nothing in the imported ontology is modified
(ADR-002).

Full definitions: [`docs/ontology/fen-ontology.ttl`](docs/ontology/fen-ontology.ttl).

## PID scheme (ADR-003)

Governance artefacts get stable, dereferenceable identifiers following the same
ARK + w3id.org pattern as GoTriple KG (D2.2, §4.5), under FEN's own NAAN:

```
ark:{FEN_NAAN}/g00042   ->  https://w3id.org/fen/id/decision/g00042          (governance decision)
ark:{FEN_NAAN}/v00042   ->  https://w3id.org/fen/id/validation/v00042        (validation record)
ark:{FEN_NAAN}/r00042   ->  https://w3id.org/fen/id/reputation-snapshot/r00042  (reputation snapshot)
ark:{FEN_NAAN}/s00042   ->  https://w3id.org/fen/id/session/s00042           (scaffolding session)
```

Resolution: `https://n2t.net/ark:{NAAN}/...` redirects to the w3id URI
(content negotiation: HTML for humans, RDF/JSON-LD for machines). Only
aggregated decision records are published — no individual votes (GDPR).
Implementation: [`services/common/pid.py`](services/common/pid.py).

## Pluggable LLM judge — decision-support only ([ADR-004](docs/adr/ADR-004-llm-judge-decision-support-only.md))

The demo mock can use **any OpenAI-compatible chat API** as an
*AI-assisted reviewer* — OpenAI, DeepSeek, a local vLLM/Ollama instance, or
GRAPHIA's own services (LLM4SSH, Quagga) if they expose such an endpoint.
Configured purely via env:

```
FEN_LLM_BASE_URL=https://api.deepseek.com/v1   # any OpenAI-compatible base URL
FEN_LLM_API_KEY=...
FEN_LLM_MODEL=deepseek-chat
```

**The boundary (ADR-004): the LLM recommends, the community decides.** The
judge may *suggest* an outcome (validated/disputed/rejected) to the DAO — it
never votes, never renders a verdict and never writes `gfen:validationStatus`.
The final decision always comes from the community DAO (Quadratic Voting),
which in production lives outside this repository (ADR-002). Within this repo
`services/common/llm.py` is called **only** by the demo mock
(`mock_fen_api/main.py`) to simulate a reviewer whose recommendation the
simulated DAO quorum adopts; neither the FEN Bridge nor the Validation Result
Consumer imports it. The judge is deliberately **generic**: it reviews the
whole candidate payload, so the same validation layer works for *any dataset
type*, not just linguistic entities. If the LLM is unavailable or indecisive,
the mock falls back to a deterministic rule — the pipeline never blocks.
Implementation: [`services/common/llm.py`](services/common/llm.py).

## Observability

All services log JSON-structured lines to stdout (`LOG_LEVEL` env var, see
[`.env.example`](.env.example)). Every service in the stack is scrapable by
Prometheus:

- HTTP services (`fen-bridge-webhook`, `mock-fen-api`, `status-api`) expose
  `GET /metrics` and a dependency-aware `GET /readyz` next to their existing
  `/healthz`;
- the consumer processes (`fen-bridge-outbound`, `validation-consumer`)
  serve the same Prometheus format on a dedicated `METRICS_PORT` (9101 /
  9102) via `prometheus_client.start_http_server` — see
  `services/common/metrics.py`.

All processes share the `fen_*` Kafka counters (processed/failed), shut down
gracefully on SIGTERM/SIGINT (producer flush, consumer close, delivery-pool
drain), and their `/metrics` endpoints are scraped by the bundled Prometheus
(`monitoring/prometheus/prometheus.yml`, five jobs). Ship the JSON logs to
Loki in production — full details in the [architecture doc](docs/architecture.md#observability).

## Positioning vs GRAPHIA's own AI services

GRAPHIA already ships LLM services — LLM4SSH (open-weight LLM on HPC/OKD),
Quagga (KGQA with RAG), TALLMesh (thematic analysis), IMeTo (fine-tuned
indexing), and the EHRI Pilot (LLM-assisted subject indexing **with
human-in-the-loop**). FEN does **not** duplicate them:

- **Scaffolding** — FEN's Agentic Scaffolding can *reuse* LLM4SSH/Quagga as
  the LLM backend instead of running its own model fleet.
- **Validation** — GRAPHIA's human-in-the-loop is *single-expert review*;
  FEN is *collective decision-making* (DAO, Quadratic Voting, reputation,
  sybil resistance). Different governance models, different niche.
- **Niche** — FEN targets community-owned, culturally sensitive data
  (low-resource languages, minority dialects, community datasets) where
  expert-only review does not scale.

## Applicability & limits

The validation layer targets the long tail — community-validated content
that expert-only curation cannot cover at scale. Where it fits
(federated SSH infrastructures, Wikidata-adjacent projects, indigenous
heritage archives under CARE principles, any crowdsourced annotation
pipeline) and where it deliberately does not (curated high-resource
domains, real-time decisions, communities below the DAO threshold) is
spelled out in [`docs/applicability-and-limits.md`](docs/applicability-and-limits.md),
together with the participation-economics model ([ADR-005](docs/adr/ADR-005-participation-model-and-dao-threshold.md)).

## Integration contract (to be verified with the consortium)

The step-by-step verification plan — what to check, in what order, with
entry/exit criteria — is in
[`docs/integration-verification-plan.md`](docs/integration-verification-plan.md).

The following assumptions come from D2.2/whitepaper and **must be confirmed
against a live GRAPHIA test instance** before production integration (see
whitepaper §7 "Request to the Consortium"):

| Contract | Current assumption | Verification needed |
|---|---|---|
| Kafka topics | `dap.entities.pending_validation.v1`, `fen.governance.decisions.v1`, `dap.entities.validated.v1`; env aliases `FEN_TOPIC_CANDIDATES` / `FEN_TOPIC_VALIDATED` ready | real DAP topic names + event bus availability |
| WP4 message schema | `EntityCandidate` (`schemas/kafka-events/`) | align with actual extracted-entity schema (no transformation) |
| Named graphs | `urn:graphia:document:{id}:graph` | DAP's real named-graph URI scheme (D2.2 §3.5) |
| SPARQL endpoint | `SPARQL_UPDATE_ENDPOINT` (Fuseki locally) | Virtuoso dialect compatibility of `build_update_query` — verified locally against OpenLink Virtuoso (`virtuoso_dialect_check.py`); production store pending |
| PID NAAN | `FEN_NAAN=99999` (dev) | registered NAAN + N2T/w3id redirects (ADR-003) |
| Deployment | docker-compose (dev) | OKD (OpenShift)/Kubernetes manifests for the DAP stack |

## Web interface (Flow 1 & Flow 2)

A zero-build web layer (plain HTML/JS + FastAPI — no Node toolchain) exposes
the two community flows:

- **Flow 1 — Community DAO portal** (`web/portal/`): submit candidates,
  watch `gfen:pending` cards, cast community votes (demo mode
  `FEN_MOCK_VOTING=community`), track quorum progress. Talks to the mock FEN
  API (`GET /candidates`, `POST /candidates/{id}/vote`). Two views:
  - the classic candidates/voting table (`index.html`);
  - the **Triadic view** (`triadic.html`): Scaffold → Consensus → Registry,
    with QV intensity voting (cost = intensity², threshold per ADR-005),
    delegation (liquid democracy, `POST /candidates/{id}/delegate`),
    reputation history + LLM-judge accuracy panel, live updates over SSE
    (`/events`), and Registry export links (TTL/JSON-LD/N-Triples/RO-Crate).
    Generic framework framing — works for any dataset type, not only
    linguistic data.
- **Flow 2 — Validation-status widget** (`web/widget/`): an embeddable
  `<fen-status>` Web Component that renders the validation badge for any
  annotation, resolved live from the RDF store via the **Status API**
  (`services/status_api`, `GET /api/v1/status/{id}` — SPARQL SELECT, read-only
  per ADR-001; `GET /api/v1/export/{id}?format=ttl|jsonld|nt|crate` for RDF /
  RO-Crate export). Click a badge for decision details (method,
  dereferenceable PID per ADR-003, ledger anchor).

The full HTTP contract is [`web/api.md`](web/api.md) — the same contract the
real FEN backend (external, ADR-002) is expected to implement, which keeps the
UI backend-agnostic. CORS is enabled (`FEN_CORS_ORIGINS`) so the widget can be
embedded in third-party pages.

Run the demo:

```bash
docker compose up --build
# portal:  http://localhost:8082/web/portal/          (classic view)
# triadic: http://localhost:8082/web/portal/triadic.html  (Scaffold→Consensus→Registry)
#          mock in QV mode: FEN_MOCK_VOTING=qv FEN_MOCK_QV_THRESHOLD=10
# widget:  http://localhost:8082/web/widget/demo.html
```

## Status & Truth Matrix (IPL 2026 Baseline)

🟢 **CI: VERIFIED & GREEN** (111 unit & integration tests passing cleanly; e2e job verified on self-hosted runner — see [`docs/self-hosted-runner.md`](docs/self-hosted-runner.md)).

Every key claim in this repository is explicitly tagged according to the IPL Readiness Audit baseline ([`docs/IPL-READINESS-AUDIT.md`](docs/IPL-READINESS-AUDIT.md)):

- **`gfen:` RDF Ontology Extension & SPARQL 1.1 Updater** — `[VERIFIED]` `[IMPLEMENTED]` Defined in `docs/ontology/fen-ontology.ttl`, tested against OpenLink Virtuoso dialect (`scripts/virtuoso_dialect_check.py`).
- **Kafka IO Event Contracts & Webhook Receiver** — `[VERIFIED]` `[IMPLEMENTED]` Pydantic models generate JSON Schemas (`schemas/kafka-events/`); at-least-once delivery semantics verified in `tests/test_kafka_io.py`.
- **Status API & Web Component Widget** — `[VERIFIED]` `[IMPLEMENTED]` Read-only REST Status API (`services/status_api`) with Turtle/JSON-LD/RO-Crate exports and `<fen-status>` Web Component (`web/widget/`).
- **Agentic Scaffolding & Quadratic Voting DAO** — `[SIMULATED]` `[MOCK]` LLM provider adapter (`services/common/llm.py`) and mock DAO (`mock_fen_api/`) simulate Phase 1 scaffolding and Phase 2 Quadratic Voting locally for demonstrations.
- **Architectural Boundary (`LLM ≠ Governance Authority`)** — `[VERIFIED]` `[IMPLEMENTED]` Code audit confirms LLM is decision-support only; LLMs cannot vote or set `gfen:validationStatus`.
- **GRAPHIA Live Network Integration** — `[PENDING EXTERNAL INTEGRATION]` `[PROPOSED]` Interface-ready microservices designed for GRAPHIA's DAP Kafka event bus and Virtuoso store (see [`docs/GRAPHIA-INTEGRATION.md`](docs/GRAPHIA-INTEGRATION.md)).

## Roadmap

- [x] FEN Bridge, Validation Result Consumer, and mock DAO implemented and unit-tested (this repo)
- [x] PID scheme for governance records (ADR-003): `services/common/pid.py`, redirect config artefact
- [x] Participation model & DAO threshold (ADR-005) + applicability analysis (`docs/applicability-and-limits.md`)
- [x] SPARQL dialect + idempotency check against a real Virtuoso (OpenLink, the GoTriple KG engine) — `scripts/virtuoso_dialect_check.py`, wired into CI
- [ ] FEN Bridge validated against a real GRAPHIA test Kafka topic + a single low-resource-language WP4 test corpus
- [ ] End-to-end demo against GRAPHIA's live Virtuoso test instance (local Virtuoso dialect check done; production store still pending)
- [ ] Real NAAN registered with the consortium; N2T/w3id redirects published
- [ ] Precision/recall evaluation, before vs. after community validation
- [ ] Formal registration as an external node in the SSH KG federation
- [ ] Accessibility work: mobile-first interface, blockchain complexity abstracted away from contributors

## Related work

- **Companion paper:** *Decentralised Agentic Governance: A Methodology for Community-Owned Linguistic Datasets and Knowledge Synthesis* (Riznyk, 2026)
- **Integrates with:** [GRAPHIA](https://graphia-ssh.eu/) — D2.2 Technical Architecture (SSH Knowledge Graph, Data Acquisition Platform)
- **Research source:** [`docs/research/graphia-tech-stack-2026-08.pdf`](docs/research/graphia-tech-stack-2026-08.pdf) — GRAPHIA technology-stack research (English edition; RDF/LPG, Ontology, DAP, OKD/HPC, LLM services), the basis for the integration audit

## Citing this repository

```bibtex
@software{riznyk2026fen,
  author  = {Riznyk, Vadym},
  title   = {{FEN} --- Triadic Synthesis Framework: A Federated Epistemic
             Node for Community-Governed Knowledge Validation},
  year    = {2026},
  url     = {https://github.com/riznykst/fen-triadic-synthesis},
  version = {0.1.0},
  note    = {Research prototype; companion implementation of
             "Decentralised Agentic Governance" (DOI pending)}
}
```

Machine-readable metadata: [`CITATION.cff`](CITATION.cff).

## License

Apache 2.0 — see [`LICENSE`](LICENSE). Chosen for compatibility with GRAPHIA's own open-source and POSI-aligned governance requirements (D2.2, §5.2.2).

## Contact

Vadym Riznyk — Independent Researcher — [riznykv@gmx.de](mailto:riznykv@gmx.de)
