# FEN — Innovation Prototyping Lab (IPL) 2026 Canonical Demonstration

**Target Event:** GRAPHIA × LUMEN Innovation Prototyping Lab 2026 (14–18 September 2026)
**Target Audience:** GRAPHIA Consortium Engineers, SSH Researchers, Knowledge Graph Architects
**Core Message:**
> **«AI scaffolds; humans and communities retain epistemic authority.»**

---

## Overview & Demo Architecture

This 3-minute vertical slice demonstrates how community-governed linguistic entities move from raw human input through AI-assisted scaffolding into decentralized community consensus (Quadratic Voting), ending as immutable, dereferenceable provenance records in the GRAPHIA knowledge graph store.

```text
Human contribution  →  Agentic scaffolding  →  Structured claim  →  Community review
        ↓                      ↓                     ↓                     ↓
   Unstructured           AI structures +         gfen:pending          Quadratic Voting
   dialect input          SHACL validates        annotation          + delegation
                                                                           ↓
RDF registry        ←      Provenance       ←  Governance decision  ←  Quorum reached
gfen:validated        dereferenceable PID        on-chain hash         outcome emitted
Virtuoso graph        ark:{NAAN}/g#####           ledger anchor
```

---

## Pre-Demo Setup (30 Seconds Before Presentation)

Start the local stack with pre-seeded mock candidates and zero-build web portal:

```bash
# Terminal 1: Start local infrastructure and services
docker compose up --build

# Verify web portal is accessible at:
# http://localhost:8082/web/portal/triadic.html
```

---

## 3-Minute Step-by-Step Script

### Minute 1: Human Contribution & Agentic Scaffolding

1. **Navigate to the Triadic Portal:**
   Open `http://localhost:8082/web/portal/triadic.html` in any modern web browser.
2. **Submit a Low-Resource Linguistic Entry:**
   - In the input field, enter a culturally specific or low-resource linguistic claim, e.g.:
     > *"Pokuttya dialect term 'ґазда' refers to a household master or traditional landowner in Western Ukrainian agrarian ethnography."*
   - Click **"Scaffold with AI Agent"**.
3. **Observe the Hard Human–AI Boundary (ADR-004):**
   - The Agentic Scaffolding service parses the input and extracts:
     - **Triple:** Subject: `ґазда`, Predicate: `hasMeaning`, Object: `traditional landowner`.
     - **Schema Hints & Relationships:** Categorized automatically.
     - **SHACL Validation:** Checked against `docs/ontology/fen-shapes.ttl` (`gfen:ScaffoldedTripleShape`).
   - **Key Point for Evaluators:** Point out that the LLM has structured the claim and provided advisory disambiguation, but **it has NOT voted or written any governance status**. The status remains strictly `gfen:pending`.

---

### Minute 2: Community Consensus & Quadratic Voting

1. **Inspect Candidate in Voting Queue:**
   - The candidate appears in the Community Consensus queue as `gfen:pending`.
2. **Demonstrate Quadratic Voting (ADR-005):**
   - Cast votes with varying intensity ($Cost = Intensity^2$).
   - Show how Quadratic Voting prevents whale/capital dominance: a vote with weight 3 costs 9 voting credits, balancing minor vs. passionate community preferences.
3. **Demonstrate Liquid Democracy Delegation:**
   - Delegate vote weight from `Voter B` to `Voter A`. Show that delegation follows delegate choices while prohibiting self-delegation or voting loops.
4. **Trigger Quorum Decision:**
   - Cast final votes reaching the quorum threshold ($Threshold = 10$).
   - Observe live Server-Sent Events (SSE) update on the UI as the mock DAO reaches consensus.

---

### Minute 3: Provenance, Registry & Embedded Widget

1. **Verify State Transition:**
   - The candidate transitions in real time from `gfen:pending` to `gfen:validated`.
2. **Inspect Provenance & PID Metadata (ADR-001 / ADR-003):**
   - Click on the decision record to view the provenance details:
     - **Governance Decision PID:** `ark:99999/g00042` -> `https://w3id.org/fen/id/decision/g00042`
     - **Reputation Snapshot PID:** `ark:99999/r00042`
     - **Ledger Anchor Hash:** `0x7f8a9b...` (On-chain hash notarization only — no full content stored on-chain, preserving GDPR right-to-erasure).
3. **Inspect SPARQL 1.1 Update Query:**
   - Show the generated SPARQL query updating the RDF named graph in Virtuoso (`urn:graphia:document:{id}:graph`).
4. **Demonstrate Embeddable Validation Widget (Flow 2):**
   - Open `http://localhost:8082/web/widget/demo.html`.
   - View the embeddable `<fen-status>` Web Component displaying a live `gfen:validated` badge next to the entity label.

---

## Evaluator Q&A Reference

- **Q: Does FEN replace GRAPHIA's Virtuoso knowledge graph?**
  - **A:** No. FEN is an external federation overlay node (ADR-002). All primary entities and graphs stay in Virtuoso; FEN only appends `gfen:validationStatus` and provenance annotations.
- **Q: What happens if the LLM hallucinated during scaffolding?**
  - **A:** Scaffolding is advisory only. The SHACL validator catches structural errors, and human community voters review and vote on the actual claim before any RDF graph update occurs.
- **Q: How does FEN handle GDPR right-to-erasure?**
  - **A:** Follows ADR-001: Only cryptographic hashes of governance decisions are anchored on-chain. Actual content resides in Virtuoso and can be redacted or modified as required by law.
