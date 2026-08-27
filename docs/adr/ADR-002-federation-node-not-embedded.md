# ADR-002: FEN integrates as a federation node, not embedded in GoTriple KG

**Status:** accepted
**Date:** 2026-08-27 (MVP design)

## Context

GRAPHIA's SSH Knowledge Graph is a federation of autonomous graphs
(OpenCitations, EHRI, GESIS, ORKG — D2.2 section 2.1), each retaining its own
governance, schema evolution, and operational rules. FEN's DAO/Quadratic Voting
infrastructure must not be operated or governed by GRAPHIA partners.

## Decision

FEN integrates as an **autonomous federation node** — the same pattern GRAPHIA
already uses for OpenCitations/EHRI/GESIS/ORKG — connected to the DAP only
through the existing Kafka event bus (two new non-blocking microservices: the
FEN Bridge and the Validation Result Consumer) and dereferenceable identifiers.
Nothing in this repository imports from, or writes to, `triple:*` classes; the
only GRAPHIA-touching artefacts are the Kafka topics that already exist in the
DAP and the additive `gfen:` namespace (`docs/ontology/fen-ontology.ttl`).

## Consequences

- No GRAPHIA partner needs to host, operate, or govern DAO infrastructure.
- The addition is fully reversible — remove the two microservices and the
  `gfen:` namespace and GRAPHIA behaves exactly as before.
- The FEN Bridge is the *only* DAP-side component that talks to the external
  FEN system; the rest of the governance stack lives outside GRAPHIA.
