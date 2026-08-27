# ADR-001: RDF anchoring, not full on-chain storage

**Status:** accepted
**Date:** 2026-08-27 (MVP design)

## Context

The Triadic Synthesis Framework (FEN) adds DAO-based community validation to
GRAPHIA's WP4 entity extraction. A governance decision must be auditable and
tamper-evident, but GRAPHIA's architecture (D2.2, ADR002) keeps Virtuoso as the
authoritative RDF core, and EU/GDPR requirements demand a right to erasure for
content.

## Decision

Blockchain is used **only to anchor a hash** of each governance decision. All
linguistic content stays in GRAPHIA's Virtuoso store under GRAPHIA's existing
data policies. In the RDF store we write governance provenance only
(`gfen:validationStatus`, `gfen:validationMethod`, `gfen:governanceDecisionId`,
`gfen:reputationSnapshot`, `gfen:ledgerAnchor`), and the on-chain value is a
literal anchor, never a content payload.

## Consequences

- No conflict with ADR002 (Virtuoso as authoritative core).
- GDPR right-to-erasure for content is preserved: only a decision hash — not
  personal or linguistic data — is immutable.
- Enforced in code: `gfen:ledgerAnchor` is the *only* field in
  `services/validation_consumer/sparql_updater.py` sourced from
  `decision.ledger_anchor`, never from raw entity content.
