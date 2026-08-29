# Applicability & Limits of the FEN Validation Layer

Where the FEN mechanism (DAO governance + federation-node pattern +
hash-anchoring + AI-assisted human review) is genuinely valuable, where it is
not, and the open questions that remain.

## What is actually innovative

No single mechanism is new: Quadratic Voting (Weil/Posner, proven in Gitcoin
Grants), hash-anchoring of decisions instead of content (OpenTimestamps-style
notarization), LLM as decision-support (industry-standard AI-assisted
moderation), ARK/w3id PIDs (established standards).

**The innovation is the institutional assembly** — DAO governance +
federation-node pattern + hash-anchoring + human-in-the-loop AI applied to
community validation of *minority-language content inside SSH knowledge
graphs*, where expert-only curation (EHRI-style single-expert review) does not
scale to community size. The architecture of GRAPHIA has no such mechanism.
Equally important is the political decision of [ADR-002](adr/ADR-002-federation-node-not-embedded.md):
an independent researcher can offer the consortium a solution that requires
*no* governance sign-off, purchase, or hosting burden to test.

## Where it applies

1. **Other federated SSH infrastructures** — DARIAH, CLARIN, and any
   OPERAS-adjacent project share the same disease: automated harvesting
   without community verification for non-mainstream languages/dialects.
2. **Wikidata/Wiktionary-adjacent projects** — patrol/rollback exists, but
   there is no formalized reputation-weighted DAO for lexicographic entries
   of rare languages. Likely the fastest non-academic entry point: the
   community already exists and needs no explanation of decentralized
   validation.
3. **Heritage archives of indigenous languages** — the best *substantive*
   fit: data sovereignty (CARE Principles, Indigenous Data Sovereignty) is a
   political requirement of the community itself. DAO governance with
   anchored provenance answers "who controls this data", not merely "is
   there an audit trail".
4. **Any crowdsourced annotation pipeline for scholarly knowledge graphs**
   — the mechanism is not tied to languages; it is tied to the problem "AI
   extracted a fact, nobody verified it" (the judge is generic, see
   `../services/common/llm.py`).

## Where it does NOT apply (and why)

- **High-resource, already curated domains** (STEM bibliographies,
  institutional archives with curator budgets) — DAO governance is pure
  overhead there; the whitepaper's argument is deliberately limited to the
  long tail.
- **Real-time decisions** — quorum voting is asynchronous by definition;
  fine for batch graph enrichment, catastrophic for anything needing a
  single real-time decision.
- **Very small communities** — with ~20 living speakers, quadratic voting
  degenerates into an ordinary committee and the DAO/blockchain machinery is
  redundant. The ontology already models `gfen:PeerReview` as the
  alternative; the threshold is formalized in
  [ADR-005](adr/ADR-005-participation-model-and-dao-threshold.md): DAO mode
  from ~20 active validators (~100 potential) upward, PeerReview below.

## The main open risk: participation economics

The DAO works only if the community has a real reason to vote repeatedly.
Reputation decay and the quadratic cost curve protect against capture — they
do not create participation. The model (ADR-005, decision 1-2) is:
intrinsic + attribution incentives (`triple:Profile` credit, portable
`gfen:reputationSnapshot` across the federation), near-zero friction
(batch queues, one-click voting, delegation), and cultural-stewardship
framing for heritage communities. **The formal incentive pilots and
participation metrics (DAU, quorum velocity) are the whitepaper v2
iteration, not this repository's scope.**
