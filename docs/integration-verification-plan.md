# Integration Verification Plan: real GRAPHIA + NAAN

How we prove the two remaining external integration items. Everything here
either needs the consortium (access grants) or can be done with local
stand-ins first (marked **NOW**). The current assumptions live in
`architecture.md` ("Integration contract (to be verified)") and
ADR-003.

## A. Real GRAPHIA (DAP Kafka + Virtuoso)

> **Store update (2026-09-16).** The engine the D2.2 DAP writes to is Virtuoso,
> but the **public** first node of the federation — the GoTriple Knowledge
> Graph, live since 1 September 2026 — is served **read-only** and runs on
> **QLever** (`https://kg-api.gotriple.eu/docs`). Two consequences for this
> plan: (a) read-only verification against the public graph is possible
> *today* and needs no consortium grant — good for A2 dialect/contract checks
> in SELECT form; (b) **no** `gfen:` write can ever land there, so the
> write-path verification below still requires a consortium test instance
> (which is what ADR-002 assumes anyway).

**Entry criteria** — the consortium grants (whitepaper §8):
1. a test-environment Kafka topic mirroring `dap.entities.pending_validation.v1`
   scoped to one low-resource-language WP4 test corpus;
2. read/update access to a test Virtuoso (or the OKD namespace for the
   services);
3. a WP4 point of contact for the message schema.

### A1. Kafka contract — verification steps
- [ ] Enumerate real topic names (`kafka-topics --list` or DAP docs) and
      diff against `docker-compose.yml` / `kafka_io.py` defaults.
- [ ] Capture **one real WP4 `EntityCandidate`** (console consumer) and diff
      it against `schemas/kafka-events/entity-candidate.schema.json`
      (field names, types, optionality, nesting).
      → If mismatch: align `services/common/messages.py` (single source of
      truth) and regenerate schemas — the bridge must consume **without
      transformation** (whitepaper §8).
- [ ] Confirm security protocol: PLAINTEXT → SASL_SSL/TLS + client certs.
      → `kafka_io.make_consumer/producer` must gain config for
      `security_protocol`, `sasl_*` (env-driven, like other settings).
- [ ] Confirm broker topic config (partitions/retention) and that our
      at-least-once semantics (acks=all, commit-after-processing) hold
      against the real broker.
- [ ] **NOW** — exercise the SASL/TLS path locally against a managed broker
      (Confluent Docker or cloud free tier) to de-risk the code change
      before touching the test instance.

### A2. SPARQL / Virtuoso dialect — verification steps
- [ ] **NOW (no grant needed)** — read-only contract check against the public
      GoTriple KG (QLever, `https://kg-api.gotriple.eu/docs`): do the D2.2 named
      graph / TRIPLE Ontology assumptions in `architecture.md` match what the
      live graph actually exposes? Record the differences either way.
- [ ] Run `build_update_query` output against **real Virtuoso**; check
      `GRAPH` in DELETE/INSERT templates, PREFIX handling, literal quoting.
- [ ] Replace `urn:graphia:document:{id}:graph` with the real DAP
      named-graph URI scheme (architecture.md contract row) and re-run the
      full loop; make sure `status_api._query_sparql` (`GRAPH ?g`) still
      resolves.
- [ ] Use `SPARQL_UPDATE_USER/PASSWORD` (already plumbed) for Virtuoso auth.
- [ ] Validate a real annotated record against `fen-shapes.ttl` — does the
      real graph's annotation pass the SHACL shapes?
- [x] **NOW** — run the dialect check locally against a Dockerized
      Virtuoso (`openlink/virtuoso-opensource`) **before** the consortium
      step: optional compose profile `virtuoso` + a smoke that applies
      `build_update_query` and SELECTs the triples back. This is the
      highest-value pre-consortium verification.

### A3. End-to-end on the test instance
- [ ] Deploy via `k8s/` manifests adapted to the OKD namespace (env:
      topics, endpoints, credentials, `FEN_NAAN`).
- [ ] Run `scripts/smoke_test.py` pointed at the test instance (or the CI
      `e2e` job on hosted runners once billing is fixed).
- [ ] Push the WP4 test corpus through the loop; verify `gfen:` triples in
      the real store and `EntityValidated` on the validated topic.
- [ ] Verify the decision PID resolves (ties into B).

## B. NAAN + PID infrastructure (ADR-003)

- [ ] **Choose the NAAN path**: request FEN's own NAAN from N2T (ARK
      registration via California Digital Library) OR a sub-range under an
      existing consortium NAAN (whitepaper §8 offers both options).
- [ ] Register the `w3id.org/fen/` namespace (perma-id/w3id.org repo):
      redirect rules for `/id/decision/*`, `/id/validation/*`,
      `/id/reputation-snapshot/*`, `/id/session/*` with content
      negotiation (HTML + RDF/JSON-LD).
- [ ] Register the N2T shoulder `ark:{NAAN}/` → forward to the w3id URLs.
- [ ] Update code: `FEN_NAAN` env in all deployments; replace
      `DEFAULT_NAAN = "99999"` in `services/common/pid.py` with the real
      value; `examples/pid-redirects.tsv` filled with real rows.
- [ ] Add a test pinning the production NAAN (`tests/test_pid.py`) so a
      typo in the registered value fails CI.
- [ ] **Verify resolution end-to-end**:
      `curl -I https://n2t.net/ark:{NAAN}/g00001` → 303 →
      `https://w3id.org/fen/id/decision/g00001` → HTML (Accept: text/html)
      and RDF (Accept: application/ld+json).
- [x] **NOW** — prepare the w3id redirect rules and the N2T registration
      request as a ready-to-submit artefact (no access needed to draft it);
      validate the rules syntax against the w3id.org conventions.

## C. Acceptance criteria (exit checklist)

- [ ] Real topics consumed with **zero schema transformation** (or an
      explicit, ADR'd delta with the model aligned).
- [ ] `gfen:` triples verifiably land in Virtuoso (SELECT back), and
      `status_api` serves real records (widget shows real status).
- [ ] PID resolution works end-to-end: n2t → w3id → HTML/RDF.
- [ ] `scripts/smoke_test.py` green against the test instance.
- [ ] ADR-003 updated: real NAAN replaces the `99999` placeholder; ADR-006
      accepted/implemented as decided.

## D. Consortium-independent integration routes (**NOW**, no access grant needed)

The plan above assumes consortium access (Kafka topics, a test SPARQL store, a
NAAN). Two further routes are available **today**, because both are published,
public and additive. They are useful even if the consortium path never opens.

### D1. SKG-IF extension route (ontology level)

GRAPHIA's own ontology deliverable states that "the GRAPHIA Ontology is built
upon the SKG-Ontology (SKG-O) and is composed of 1. necessary extensions of
SKG-O and 2. the collection of mappings between the data models of existing KGs
and SKG-O" (D2.1, p. 21) and that "these extensions could be aligned under a
common namespace, forming the GRAPHIA Ontology as **an extension for SSH of SKG
Ontology**" (p. 22). SKG-IF publishes the extension process and its rules:

- process and participation rules (<https://skg-if.github.io/extensions/>):
  *Shared Interest/Need* (a collective need, not an individual one) and
  *Non-Interference* (additive; no duplication of what belongs elsewhere);
- repository template and binding folder/versioning rules
  (<https://skg-if.github.io/ext-tmpl/structure.html>), giving permanent URL
  patterns under `https://w3id.org/skg-if/extension/<acronym>/…`;
- core model: SKG-O at `https://w3id.org/skg-if/ontology/` (six modules:
  agent, data-source, grant, research-product, topic, venue), SHACL at
  `https://w3id.org/skg-if/validation/shacl`.

**Our staging package:** [`integrations/skg-if-extension/`](../integrations/skg-if-extension/README.md)
— draft ontology (`ValidationAssertion` + one relation to
`skgo:research-product`), SHACL shapes, JSON-LD context and an SSSOM mapping
from the working `gfen:` namespace. **Not submitted**: the *Shared Interest*
rule requires a co-proponent or a documented community need first.

- [ ] Decide the extension acronym and the scope statement (collective need).
- [ ] Complete the template folders (`current/` copies, `interoperability-framework/`, `api/`, `examples/`).
- [ ] Cross-check the SSSOM mapping against the SKG-O modules (agent, research-product, topic).
- [ ] Open the application issue on `github.com/skg-if/extensions`.

### D2. Data Contract route (LUMEN data-mesh level)

LUMEN's data model is deliberately minimal: a **Data Product** (DPROD + DCAT)
governed by exactly one **Data Contract**, and internal curation stays with the
community ("communities remain fully responsible for the internal curation and
structure of the encapsulated resources", D4.2 p. 18). LUMEN adopts **ODCS v3**
as-is (<https://bitol-io.github.io/open-data-contract-standard/latest/>) through
a Required/Recommended/Conditional profile, and ODCS
`customProperties` is documented as the "extension mechanism for governance
metadata not covered by standard fields" — the natural place to declare
**how a node validates the knowledge it contributes**.

- [ ] Draft the node's Data Product (DPROD/DCAT) description with honest values
      (`lifecycleStatus`, `dataProductOwner`, endpoints that actually exist).
- [ ] Draft the ODCS contract skeleton, marking every simulated component
      (`simulated: true`; the anchor stays `0xMOCK` until a ledger exists).
- [ ] Ask the LUMEN data-model authors the four questions in
      `d42-data-contract-structure.md` §5 (`customProperties` vs `quality[]`,
      canonical `quality[].type`, `roles[]` vocabulary, publishing a validation
      record template next to the contract).

### D3. GoTriple KG (read-only, live)

The public node is **read-only and QLever-based** (<https://kg-api.gotriple.eu/docs>):
it can validate our *query* assumptions today but can never accept `gfen:`
writes — which is exactly why the external-node design in ADR-002 is a
constraint, not a preference.

## E. Ownership

| Item | Owner |
|---|---|
| Test-instance access (topics, corpus, Virtuoso/QLever, OKD ns) | consortium (whitepaper §8 request) |
| NAAN/w3id/N2T registration | FEN (us) + consortium sign-off |
| Code alignment (messages, kafka auth, pid, shapes) | us |
| Dialect / SASL pre-checks (**NOW**) | us |
| SKG-IF extension application (D1) | us (+ co-proponent for *Shared Interest*) |
| Data Contract draft + questions to LUMEN authors (D2) | us |
