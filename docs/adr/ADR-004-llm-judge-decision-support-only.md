# ADR-004: LLM judge is decision-support only — never a voter

**Status:** accepted
**Date:** 2026 (pre-push formalization, audit feedback)

## Context

The whitepaper's core thesis is that WP4 extracts entities *automatically*
without human validation, and FEN restores the human-in-the-loop. The MVP
adds a pluggable LLM judge (`services/common/llm.py`, OpenAI-compatible API)
to the demo stack. Without an explicit boundary, a reviewer could read this
as replacing one automation (WP4 NLP) with another (an LLM that "decides"),
which would contradict the project's own argument — a question GRAPHIA
partners (notably OpenCitations/EHRI, which are sensitive to automated
governance) would raise within minutes.

## Decision

1. **The LLM is decision-support only.** It may *recommend* an outcome
   (validated/disputed/rejected) and help structure a submission during
   Agentic Scaffolding. It **never votes, never renders a governance verdict,
   and never writes `gfen:validationStatus`**.
2. **The final verdict always comes from the community DAO** (Quadratic
   Voting), which in production lives entirely outside this repository
   (ADR-002).
3. **Call site within this repository:** `services/common/llm.py` is
   imported and invoked **only** by the demo mock (`mock_fen_api/main.py`)
   to simulate an AI-assisted reviewer whose recommendation the *simulated*
   DAO quorum adopts. Neither the FEN Bridge
   (`services/fen_bridge/`) nor the Validation Result Consumer
   (`services/validation_consumer/`) imports or calls it.
4. **The only writer of governance provenance** in the named graph is the
   Validation Result Consumer, executing decisions received on
   `fen.governance.decisions.v1` — never an LLM output directly.
5. When a real DAO is wired up, the LLM may remain as scaffolding-side
   decision support (e.g., helping contributors draft/justify candidates);
   its output must never be treated as quorum.

## Consequences

- The whitepaper's human-in-the-loop thesis stays intact: automation
  (LLM) *assists*, the community *decides*.
- Answers the "who decides?" scrutiny in 30 seconds: the community DAO,
  external and self-governed (ADR-002).
- The demo remains useful without an API key: the deterministic rule is the
  simulated quorum fallback.
- `FEN_LLM_*` env vars are demo-scoped today; the same provider may later
  serve Agentic Scaffolding, still without voting rights.
