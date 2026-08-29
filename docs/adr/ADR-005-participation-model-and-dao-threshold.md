# ADR-005: Participation model and DAO applicability threshold

**Status:** accepted
**Date:** 2026 (post-MVP formalization, whitepaper iteration input)

## Context

The whitepaper's governance thesis rests on the community DAO, but two
questions were not answered explicitly:

1. **Participation economics** — why would a speaker of a rare language
   spend time voting on extracted entities? Reputation decay and the
   quadratic cost curve protect against capture; they do not by themselves
   create a reason to participate.
2. **Applicability threshold** — for very small communities (e.g. ~20
   living speakers), quadratic voting degenerates into an ordinary
   committee and the DAO machinery becomes overhead. The ontology already
   models `gfen:PeerReview` as an alternative method; the choice between
   methods was never formalized.

## Decision

1. **No token economy in the MVP.** Incentives are intrinsic and
   attribution-based:
   - contributor identity reuses `triple:Profile` — visible, citable
     credit inside the SSH Knowledge Graph (academic currency);
   - reviewer reputation is a **portable asset** (`gfen:reputationSnapshot`,
     ADR-003) — it carries across federation nodes, so voting for one's own
     community earns weight in others' (reciprocity loop);
   - cultural-stewardship framing for heritage communities (CARE
     Principles / Indigenous Data Sovereignty): participation is the
     exercise of data sovereignty, not donated labour.
2. **Near-zero participation friction.** Async batch review queues,
   one-click voting, mobile-first UX, and a **delegation option** (a
   community-elected delegate votes with pooled reputation during
   low-activity periods). The quadratic cost curve is capture-resistance
   only — base participation must cost (almost) nothing.
3. **DAO applicability threshold.** DAO/Quadratic-Voting mode requires a
   minimum active validator pool per community/deployment. Default: **>= 20
   distinct active validators** (community size on the order of >= 100
   potential validators). Below the threshold, deployments SHOULD use
   `gfen:PeerReview` (expert/committee) mode. The threshold is a FEN-side
   deployment parameter — tunable per community, never a code constant.
4. **Real-time decisions are out of scope.** The pipeline is asynchronous
   batch enrichment only; nothing in this repo targets single decisions in
   real time.

## Consequences

- Honest positioning: DAO machinery is a tool for mid-to-large
  long-tail communities, not a universal answer (see
  `../applicability-and-limits.md`).
- No speculative elements (no token, no staking) — GDPR/EOSC-aligned and
  consortium-friendly.
- Whitepaper v2 should state the threshold and the incentive model
  explicitly; this ADR is the input for that iteration.
