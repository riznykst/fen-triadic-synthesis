# LUMEN-style Data Contract for a FEN node — draft example

**Draft, not a published contract.** This folder holds one machine-readable
example of how a FEN node could present itself in the LUMEN data mesh: a **Data
Product** (DPROD + DCAT) governed by exactly one **Data Contract** (ODCS v3
profile), following the structure verified in LUMEN **D4.2** "LUMEN Data Model"
(Zenodo `records/18244957`, pp. 17–19 and 46–56).

## What the example demonstrates

| Element | Where | What it says |
|---|---|---|
| Data Product + one contract | `dprod:DataProduct`, `dprod:dataProductOwner`, `dprod:lifecycleStatus` | the node is a governed unit of exposure; the owner is accountable; status is honest (`in progress`) |
| Validation declaration | `odcs:customProperties` → `validationSemantics` | the vocabulary used to state *how* a contributed claim was validated (`cvkg:ValidationAssertion`: pending / validated / disputed / rejected; community vote / expert review / automated) |
| Testable expectations | `odcs:quality` | "every contributed statement carries a validation assertion"; "rejected and disputed assertions remain in the graph with a date" |
| Who may do what | `odcs:roles` | producer · validator · challenger · consumer — the distinction LUMEN's `roles[]` may or may not already support (one of the open questions) |
| Honest simulation markers | `simulatedInfrastructure`, `lifecycleStatus`, placeholder endpoints | the mock DAO, the `0xMOCK` anchor and the development NAAN stay visible instead of being dressed up as production |

`customProperties` is used deliberately: LUMEN's own profile describes it as the
"extension mechanism for governance metadata not covered by standard fields"
(D4.2, p. 56). Nothing here changes LUMEN's data model, DPROD, DCAT or ODCS.

## Open questions for the LUMEN data-model authors

1. Is `customProperties` the intended place for a validation declaration, or
   should it live in `quality[]`?
2. Does `quality[].type` have a canonical value for a
   "provenanced/validated contribution"?
3. Does `roles[]` already distinguish *producer*, *validator* and *challenger*?
4. May a node publish its validation-record template next to its Data Contract?

## Validation status of this file

- JSON parses; JSON-LD parses into RDF with the contexts inlined (offline-safe).
- **Not** validated against a LUMEN/ODCS validator — no public one is available in
  this toolchain. The structure follows the field tables in D4.2; expect the
  property names to be adjusted once the data-model authors answer the questions
  above. Endpoints use the RFC 2606 reserved domain `example.org` on purpose.
- The companion validation records are in
  [`../skg-if-extension/examples/validation-record.example.jsonld`](../skg-if-extension/examples/validation-record.example.jsonld)
  and *do* pass the SHACL shapes staged in that package.
