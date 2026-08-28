# FEN — Triadic Synthesis Framework

**A federated governance layer for community-validated linguistic data, designed to integrate with the [GRAPHIA](https://graphia-project.eu) SSH Knowledge Graph as an autonomous federation node.**

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-MVP%20implemented-green.svg)](#status)
[![GRAPHIA](https://img.shields.io/badge/integrates%20with-GRAPHIA%20D2.2-informational.svg)](docs/whitepaper.docx)

---

## What this is

WP4 of the GRAPHIA project extracts entities and relations from full-text SSH documents automatically, via AI/NLP services, and commits them directly into the GoTriple Knowledge Graph — with no step for human review, cultural verification, or contributor attribution. That's fine for well-resourced content. It systematically underserves low-resource languages, minority dialects, and culturally specific material.

FEN (Federated Epistemic Node) closes that gap with a three-phase pipeline:

1. **Agentic Scaffolding** — an AI agent (built on ElizaOS) guides contributors in structuring linguistic knowledge, without ever deciding on their behalf.
2. **Decentralised Validation** — a DAO, using Quadratic Voting and reputation-weighted review, decides whether a candidate entity is accepted, disputed, or rejected. The community remains the final arbiter of meaning.
3. **Immutable Integration** — the governance decision is anchored (hash only) on-chain and exposed as a dereferenceable PID ([ADR-003](docs/adr/ADR-003-fen-pid-scheme.md)), while the underlying content stays in GRAPHIA's authoritative RDF store.

**FEN does not replace or modify any part of GRAPHIA's core infrastructure.** It connects as an external federation node — the same architectural pattern GRAPHIA already uses for OpenCitations, EHRI, GESIS, and ORKG (D2.2, §2.1) — and touches the DAP only through two new, non-blocking microservices (the FEN Bridge and the Validation Result Consumer) on the existing Kafka event bus ([ADR-002](docs/adr/ADR-002-federation-node-not-embedded.md)).

## Why it matters

> Current industrial paradigms largely treat language as a raw resource, harvested at scale with limited regard for cultural context or community agency.

This project is the applied counterpart to the academic paper *"Decentralised Agentic Governance: A Methodology for Community-Owned Linguistic Datasets and Knowledge Synthesis"* (Riznyk, 2026), which is submitted separately for journal publication and is not included in this repository. The consortium-facing [`docs/whitepaper.docx`](docs/whitepaper.docx) (also as [`docs/FEN-Whitepaper-Triadic-Synthesis.pdf`](docs/FEN-Whitepaper-Triadic-Synthesis.pdf)) summarises that framework specifically for the GRAPHIA integration proposal — read it first if you're evaluating this repo on behalf of the consortium.

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
   [ Agentic Scaffolding (ElizaOS) → DAO / Quadratic Voting ]
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

Candidates are published immediately with `gfen:pending` — the pipeline never blocks on a vote. See the [whitepaper](docs/whitepaper.docx), §4, for the full flow and the [architecture doc](docs/architecture.md) for details.

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
├── AGENT_PLAN.md                    step-by-step build plan for an AI coding agent
├── LICENSE                          Apache 2.0
├── docker-compose.yml                full local dev stack (Kafka, Fuseki, all services)
├── .env.example                      every configurable env var, with local-dev defaults
├── requirements-common.txt           combined deps for running tests locally
├── .github/
│   └── workflows/ci.yml              CI: unit tests (Python 3.10–3.12) + docker-compose e2e smoke test
├── docs/
│   ├── whitepaper.docx               consortium-facing integration proposal
│   ├── architecture.md               quick-reference diagrams + component map
│   ├── adr/
│   │   ├── ADR-001-rdf-anchoring-not-full-onchain.md
│   │   ├── ADR-002-federation-node-not-embedded.md
│   │   ├── ADR-003-fen-pid-scheme.md
│   │   └── ADR-004-llm-judge-decision-support-only.md
│   ├── user-stories.md               two typical use cases for the validation layer
│   ├── images/
│   │   ├── story1-validation-flow.svg     user-story infographic (community validation flow)
│   │   └── story2-validation-overlay.svg  user-story infographic (validation overlay)
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
│   └── smoke_test.py                 e2e smoke test against the docker-compose stack (CI `e2e` job)
├── services/
│   ├── common/                       shared models, gfen: constants, PID helpers, Kafka IO (at-least-once),
│   │                                JSON logging (`logging_config.py`), Prometheus metrics (`metrics.py`)
│   ├── fen_bridge/                   outbound consumer + inbound webhook (2 containers)
│   └── validation_consumer/          SPARQL Update logic + Kafka consumer
├── mock_fen_api/                     demo DAO stand-in — NOT production governance
├── k8s/                              Kubernetes/OKD manifests: 3 Deployments + ConfigMap + Secret
├── tests/                            61 tests, all offline (mocked Kafka/HTTP/LLM, in-memory RDF)
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
[`.env.example`](.env.example)), and the two HTTP services (`fen-bridge-webhook`,
`mock-fen-api`) expose Prometheus metrics on `GET /metrics` and a dependency-aware
`GET /readyz` next to their existing `/healthz`. Consumers (outbound,
validation-consumer) log-count the same Kafka counters and shut down gracefully
on SIGTERM/SIGINT (producer flush, consumer close, delivery-pool drain). Scrape
`/metrics` with Prometheus/Grafana and ship the JSON logs to Loki in production —
full details in the [architecture doc](docs/architecture.md#observability).

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

## Integration contract (to be verified with the consortium)

The following assumptions come from D2.2/whitepaper and **must be confirmed
against a live GRAPHIA test instance** before production integration (see
whitepaper §7 "Request to the Consortium"):

| Contract | Current assumption | Verification needed |
|---|---|---|
| Kafka topics | `dap.entities.pending_validation.v1`, `fen.governance.decisions.v1`, `dap.entities.validated.v1` | real DAP topic names + event bus availability |
| WP4 message schema | `EntityCandidate` (`schemas/kafka-events/`) | align with actual extracted-entity schema (no transformation) |
| Named graphs | `urn:graphia:document:{id}:graph` | DAP's real named-graph URI scheme (D2.2 §3.5) |
| SPARQL endpoint | `SPARQL_UPDATE_ENDPOINT` (Fuseki locally) | Virtuoso dialect compatibility of `build_update_query` |
| PID NAAN | `FEN_NAAN=99999` (dev) | registered NAAN + N2T/w3id redirects (ADR-003) |
| Deployment | docker-compose (dev) | OKD (OpenShift)/Kubernetes manifests for the DAP stack |

## Status

🟢 **MVP implemented, unit-tested, runnable via `docker compose up`.** All Kafka
message contracts, the `gfen:` ontology extension, the FEN Bridge (outbound +
webhook), the Validation Result Consumer's SPARQL Update logic, and a mock DAO for
local demos are in place — tests pass offline (mocked Kafka/HTTP/LLM, in-memory RDF
via `rdflib`). Kafka delivery is **at-least-once** (`acks=all`, idempotent
producer, commit-after-processing — see [`docs/architecture.md`](docs/architecture.md)),
and an end-to-end smoke test (`scripts/smoke_test.py`) validates the full loop
against the docker-compose stack (CI `e2e` job).

**Not yet done:** integration against a live GRAPHIA test instance (real Kafka
topics, real Virtuoso), replacing the mock DAO with the real Quadratic Voting
contract, and registering a real NAAN for FEN PIDs. See the "Request to the
Consortium" section of the [whitepaper](docs/whitepaper.docx) for what's needed
to start that.

## Roadmap

- [x] FEN Bridge, Validation Result Consumer, and mock DAO implemented and unit-tested (this repo)
- [x] PID scheme for governance records (ADR-003): `services/common/pid.py`, redirect config artefact
- [ ] FEN Bridge validated against a real GRAPHIA test Kafka topic + a single low-resource-language WP4 test corpus
- [ ] End-to-end demo against a live Virtuoso test instance (currently only against Fuseki, locally)
- [ ] Real NAAN registered with the consortium; N2T/w3id redirects published
- [ ] Precision/recall evaluation, before vs. after community validation
- [ ] Formal registration as an external node in the SSH KG federation
- [ ] Accessibility work: mobile-first interface, blockchain complexity abstracted away from contributors

## Related work

- **Companion paper:** *Decentralised Agentic Governance: A Methodology for Community-Owned Linguistic Datasets and Knowledge Synthesis* (Riznyk, 2026)
- **Integrates with:** [GRAPHIA](https://graphia-project.eu) — D2.2 Technical Architecture (SSH Knowledge Graph, Data Acquisition Platform)
- **Research source:** [`docs/research/graphia-tech-stack-2026-08.pdf`](docs/research/graphia-tech-stack-2026-08.pdf) — GRAPHIA technology-stack research (English edition; RDF/LPG, Ontology, DAP, OKD/HPC, LLM services), the basis for the integration audit

## License

Apache 2.0 — see [`LICENSE`](LICENSE). Chosen for compatibility with GRAPHIA's own open-source and POSI-aligned governance requirements (D2.2, §5.2.2).

## Contact

Vadym Riznyk — Independent Researcher — [riznykv@gmx.de](mailto:riznykv@gmx.de)
