# Integration Verification Plan: real GRAPHIA + NAAN

How we prove the two remaining external integration items. Everything here
either needs the consortium (access grants) or can be done with local
stand-ins first (marked **NOW**). The current assumptions live in
`architecture.md` ("Integration contract (to be verified)") and
ADR-003.

## A. Real GRAPHIA (DAP Kafka + Virtuoso)

**Entry criteria** — the consortium grants (whitepaper §7):
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
      transformation** (whitepaper §7).
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
- [ ] Run `build_update_query` output against **real Virtuoso**; check
      `GRAPH` in DELETE/INSERT templates, PREFIX handling, literal quoting.
- [ ] Replace `urn:graphia:document:{id}:graph` with the real DAP
      named-graph URI scheme (architecture.md contract row) and re-run the
      full loop; make sure `status_api._query_sparql` (`GRAPH ?g`) still
      resolves.
- [ ] Use `SPARQL_UPDATE_USER/PASSWORD` (already plumbed) for Virtuoso auth.
- [ ] Validate a real annotated record against `fen-shapes.ttl` — does the
      real graph's annotation pass the SHACL shapes?
- [ ] **NOW** — run the dialect check locally against a Dockerized
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
      existing consortium NAAN (whitepaper §7 offers both options).
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
- [ ] **NOW** — prepare the w3id redirect rules and the N2T registration
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

## D. Ownership

| Item | Owner |
|---|---|
| Test-instance access (topics, corpus, Virtuoso, OKD ns) | consortium (whitepaper §7 request) |
| NAAN/w3id/N2T registration | FEN (us) + consortium sign-off |
| Code alignment (messages, kafka auth, pid, shapes) | us |
| Dialect / SASL pre-checks (**NOW**) | us |
