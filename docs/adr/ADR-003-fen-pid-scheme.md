# ADR-003: ARK + w3id.org PID scheme for FEN governance records

**Status:** accepted (session decision record, 2026)
**Supersedes:** the earlier draft that showed `gfen:governanceDecisionId` as a
literal DAO proposal/tx id (`"dao-tx-0x..."`) in a `fen:` (not `gfen:`) namespace.

## Context

Governance decisions of the FEN DAO need stable, dereferenceable identifiers
so they can be cited, validated, and linked from `oa:Annotation` instances in
the GoTriple KG. GRAPHIA D2.2 section 4.5 already uses the ARK + w3id.org
pattern for GoTriple resources; FEN follows the same pattern under its **own
NAAN**, because FEN is a federation node (ADR-002), not part of GoTriple KG.

A PID must not be tied to a URL or to a specific blockchain explorer — the
lesson GRAPHIA draws from the old GoTriple scheme
(`https://www.gotriple.eu/documents/<PRIMARY_ID>`) and from the purl.org/OCLC
history. The on-chain tx hash is an *attribute* of a record
(`gfen:ledgerAnchor`), never its identifier.

## Decision

1. **NAAN.** FEN registers its own NAAN with the consortium (whitepaper
   section 7); local dev uses `FEN_NAAN=99999` (docker-compose.yml).
2. **Assigned-name prefixes** (5-digit zero-padded sequence):

   | Prefix | Entity | w3id URI |
   |---|---|---|
   | `g` | governance decision (DAO outcome) | `https://w3id.org/fen/id/decision/gNNNNN` |
   | `v` | validation record (entity + decision + snapshot) | `https://w3id.org/fen/id/validation/vNNNNN` |
   | `r` | reputation snapshot at decision time | `https://w3id.org/fen/id/reputation-snapshot/rNNNNN` |
   | `s` | scaffolding session that produced the candidate | `https://w3id.org/fen/id/session/sNNNNN` |

   Contributors are **not** re-numbered: identity reuses `triple:Profile`
   (FEN identity is ORCID-based) — no duplicate identity layer.
3. **Resolution.** `https://n2t.net/ark:{NAAN}/{assigned}` redirects to the
   w3id URI; content negotiation serves HTML for humans and RDF/JSON-LD for
   machines.
4. **Decision record.** The dereferenceable resource is an aggregated record
   (class `gfen:GovernanceDecision`): `appliesTo`, `quorumReached`, `outcome`,
   `validationMethod`, `decidedAt`, link to the reputation snapshot,
   `prov:wasGeneratedBy` (session), and `ledgerAnchor` as a literal attribute.
   Individual votes are never published (GDPR).
5. **In the annotation.** `gfen:governanceDecisionId` and
   `gfen:reputationSnapshot` are dereferenceable IRIs, not literals.

## Consequences

- Three trust levels for one record: PID (stable citation), RDF body
  (GDPR-compatible aggregate), `ledgerAnchor` (optional cryptographic
  integrity check).
- If the chain changes or the contract migrates, only `ledgerAnchor` breaks —
  the PID and the record's citability in the KG survive.
- Implementation: `services/common/pid.py` (`mint_ark`, `n2t_uri`,
  `w3id_uri`); redirect configuration to be published as an artefact
  (`examples/pid-redirects.tsv`) once a real NAAN is granted.
