"""Mock FEN API — stands in for the real Agentic Scaffolding + DAO
Quadratic Voting system, for local development and consortium demos only.

Accepts batches of EntityCandidate on POST /candidates, then after a
configurable delay calls back FEN Bridge's inbound webhook with a
synthetic GovernanceDecision.

Decision logic (in priority order):
1. If an OpenAI-compatible LLM endpoint is configured (FEN_LLM_BASE_URL —
   OpenAI, DeepSeek, local vLLM/Ollama, or GRAPHIA services such as
   LLM4SSH/Quagga exposing such an API), the LLM judges the candidate
   (validated/disputed/rejected). This works for ANY dataset payload, not
   just linguistic entities.
2. Otherwise a deterministic placeholder rule applies (non-empty
   entity_label -> validated, else rejected).

This MUST NOT be mistaken for real DAO/Quadratic Voting governance, which
lives entirely outside this repository (see ADR-002).

Runs as the `mock-fen-api` container (see docker-compose.yml).
"""
from __future__ import annotations

import itertools
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests
from fastapi import FastAPI

from services.common.llm import LLMConfig, chat_completion, parse_outcome

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mock FEN API (demo DAO stand-in — not production governance)")

WEBHOOK_URL = os.getenv("FEN_BRIDGE_WEBHOOK_URL", "http://localhost:8101/webhook/decision")
DECISION_DELAY_S = float(os.getenv("MOCK_FEN_DECISION_DELAY_S", "3"))
MAX_WORKERS = int(os.getenv("MOCK_FEN_MAX_WORKERS", "8"))
WEBHOOK_MAX_RETRIES = int(os.getenv("MOCK_FEN_WEBHOOK_RETRIES", "3"))

_decision_counter = itertools.count(1)
_reputation_counter = itertools.count(1)

# Bounded pool instead of an unbounded daemon thread per candidate
# (audit finding: daemon threads + sleep can pile up without a limit).
_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="mock-fen")

# Optional OpenAI-compatible LLM judge (any provider; DeepSeek by example).
_llm_config = LLMConfig()

_LLM_SYSTEM = (
    "You are a strict validator for a community data-governance layer. "
    "Review the candidate record for factual quality and cultural sensitivity. "
    "Reply with exactly one word: validated, disputed, or rejected."
)


def _decide_outcome(candidate: dict) -> str:
    """LLM judge with deterministic rule fallback. Generic — works for any
    dataset payload, not just linguistic entities.
    """
    if _llm_config.enabled:
        answer = chat_completion(
            _llm_config,
            _LLM_SYSTEM,
            json.dumps(candidate, ensure_ascii=False),
        )
        outcome = parse_outcome(answer, ("validated", "disputed", "rejected"))
        if outcome:
            logger.info("LLM judge decided %r for %s", outcome, candidate.get("annotation_id"))
            return outcome
        logger.warning(
            "LLM judge unavailable/indecisive for %s; falling back to rule",
            candidate.get("annotation_id"),
        )
    # Placeholder rule standing in for real Quadratic Voting. Replace only
    # this branch when wiring up a real DAO backend.
    return "validated" if candidate.get("entity_label") else "rejected"


def _fake_decide(candidate: dict) -> dict:
    decision_seq = next(_decision_counter)
    reputation_seq = next(_reputation_counter)
    return {
        "annotation_id": candidate["annotation_id"],
        "document_id": candidate.get("document_id"),
        "decision_id": f"g{decision_seq:05d}",
        "outcome": _decide_outcome(candidate),
        "method": "quadratic_voting",
        "quorum_reached": True,
        "reputation_snapshot_id": f"r{reputation_seq:05d}",
        "ledger_anchor": f"0xMOCK{decision_seq:08x}",
        "decided_at": datetime.now(timezone.utc).isoformat(),
    }


def _deliver_decision_after_delay(candidate: dict) -> None:
    """Wait the configured delay, then deliver the decision to the webhook
    with a few retries. A lost demo decision is logged, not fatal.
    """
    time.sleep(DECISION_DELAY_S)
    decision = _fake_decide(candidate)
    for attempt in range(WEBHOOK_MAX_RETRIES):
        try:
            resp = requests.post(WEBHOOK_URL, json=decision, timeout=10)
            resp.raise_for_status()
            logger.info(
                "delivered mock decision for %s -> %s",
                candidate["annotation_id"],
                decision["outcome"],
            )
            return
        except requests.RequestException:
            logger.exception(
                "failed to deliver mock decision for %s (attempt %d/%d)",
                candidate.get("annotation_id"),
                attempt + 1,
                WEBHOOK_MAX_RETRIES,
            )
            if attempt < WEBHOOK_MAX_RETRIES - 1:
                time.sleep(0.5 * (attempt + 1))


@app.post("/candidates")
def submit_candidates(payload: dict):
    candidates = payload.get("candidates", [])
    for candidate in candidates:
        _executor.submit(_deliver_decision_after_delay, candidate)
    return {"accepted": len(candidates)}


@app.get("/healthz")
def healthz():
    return {"status": "ok", "note": "this is a DEMO stand-in for FEN's real DAO — see ADR-002"}
