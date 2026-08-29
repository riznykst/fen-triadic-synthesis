# ADR-006 (DRAFT): Tokenless challenge window — optional framework feature

**Status:** proposed / draft — not accepted. Open questions at the bottom.
**Date:** 2026-08-29

## Context

Recommendation #7 (flow roadmap, docs/BACKLOG.md) proposes a challenge /
dispute timelock before a QV decision is final. A staking-based challenge
conflicts with [ADR-005](ADR-005-participation-model-and-dao-threshold.md)
("no token economy in the MVP", no speculative elements). This draft
specifies a **tokenless** challenge mechanism that keeps ADR-005 intact and
is **optional per deployment** — a governance policy, not a framework
mandate.

The current flow (whitepaper §4.2, mock `cast_vote`): quorum/threshold
reached → decision delivered to the webhook → Validation Result Consumer
writes `gfen:validationStatus` → record is final. There is no window for
the community to contest an outcome before it lands in the graph.

## Decision (draft)

1. **Optional feature.** The challenge window is a FEN-side deployment
   policy, enabled by a configuration parameter (e.g.
   `FEN_CHALLENGE_WINDOW_S`, default `0` = disabled → current behavior
   unchanged). No existing deployment changes.
2. **Tokenless challenge — reputation lock.** A challenger must hold
   reputation (ADR-005 incentives) and *locks* a fraction of it (proposed
   default: 10% of their balance, min 1 point) for the challenge period:
   - challenge **succeeds** (outcome flips) → the locked reputation is
     returned, the decision is re-opened as `gfen:disputed` and goes to an
     **appeal round**: a second QV vote with a higher threshold (proposed
     default 2× the original threshold);
   - challenge **fails** (frivolous) → a penalty (proposed default: 50% of
     the locked amount) is deducted from the challenger's reputation —
     anti-spam without tokens.
3. **Timeline.** `pending → (threshold reached) → challengeable
   (window S) → finalize (webhook + gfen write)`. If a challenge arrives
   inside the window, finalization is deferred until the appeal round
   concludes. Until finalization the entity **stays `gfen:pending`** —
   the "no blocking points" property of the pipeline is preserved: the
   candidate was already published; only the *finality* of the decision is
   delayed (bounded by the window + appeal duration).
4. **Scope.** Enforcement lives in the FEN-side governance layer (mock
   first, real DAO later, per ADR-002). The DAP side (Bridge/Consumer)
   is untouched: it still receives exactly one final decision per entity.
5. **Ontology (proposed, not yet applied).** Reuse the existing
   `gfen:disputed` status; optionally add
   `gfen:challengeWindowEnd` (xsd:dateTime) as provenance metadata so the
   finality horizon is visible to consumers. No core class changes.

## Consequences

- **Compatible with ADR-005**: no tokens, no staking, no speculative
  elements; the cost of a challenge is reputation, which is already the
  incentive currency of the framework.
- **Optional**: default-off keeps the current immediate-finality behavior;
  deployments with mature communities may opt in.
- **Anti-spam**: the reputation penalty makes frivolous challenges costly
  without introducing a payment rail.
- **Finality latency**: bounded (window + appeal round); documented per
  deployment; the pipeline itself never stalls.
- **Sybil note**: challenge power scales with reputation, so acquisition
  of reputation (not tokens) bounds it — consistent with ADR-005 and the
  future identity-provider interface (#4 in the roadmap).

## Open questions (for acceptance)

1. Default window duration (24h?) and whether the appeal threshold should
   scale with the number of challengers or stay a fixed 2×.
2. Who may challenge: any reputation holder, or only voters of the
   *losing* outcome? (Symmetric vs. loser-only challenges.)
3. Where the challenge window is observed by the UI: a countdown on the
   candidate card / widget (`gfen:challengeWindowEnd`), driven by SSE.
4. Interaction with ADR-003: the `decision_id` PID is minted at
   finalization, so a challenged decision simply finalizes later — no
   re-minting needed. Confirm this interpretation.
5. Should a successful challenge that ends in `rejected` award anything to
   the challenger (e.g., +1 "watchdog" reputation), or is the return of
   the lock the only reward?
