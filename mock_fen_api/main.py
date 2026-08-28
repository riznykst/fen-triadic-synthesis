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
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import requests
from fastapi import FastAPI

from services.common.llm import LLMConfig, chat_completion, parse_outcome
from services.common.logging_config import log_level_from_env, setup_logging
from services.common.metrics import (
    MOCK_CANDIDATES_ACCEPTED,
    MOCK_DECISIONS_DELIVERED,
    MOCK_DELIVERY_FAILURES,
    MOCK_DELIVERY_SECONDS,
    MOCK_LLM_JUDGE_CALLS,
    metrics_response,
)

setup_logging("mock-fen-api", level=log_level_from_env())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Graceful shutdown: on SIGTERM/SIGINT uvicorn runs this teardown, which
    stops the delivery pool from accepting new work and waits for in-flight
    deliveries (``executor.shutdown(wait=True)``). TestClient used without the
    ``with`` block never triggers the lifespan, so tests keep the pool alive.
    """
    yield
    _shutdown_executor()


app = FastAPI(title="Mock FEN API (demo DAO stand-in — not production governance)", lifespan=lifespan)

WEBHOOK_URL = os.getenv("FEN_BRIDGE_WEBHOOK_URL", "http://localhost:8101/webhook/decision")
DECISION_DELAY_S = float(os.getenv("MOCK_FEN_DECISION_DELAY_S", "3"))
MAX_WORKERS = int(os.getenv("MOCK_FEN_MAX_WORKERS", "8"))
WEBHOOK_MAX_RETRIES = int(os.getenv("MOCK_FEN_WEBHOOK_RETRIES", "3"))

_decision_counter = itertools.count(1)
_reputation_counter = itertools.count(1)

# Bounded pool instead of an unbounded daemon thread per candidate
# (audit finding: daemon threads + sleep can pile up without a limit).
# Lazily created and re-creatable so a graceful shutdown of the pool
# (FastAPI lifespan -> _shutdown_executor) never bricks the process.
_executor: Optional[ThreadPoolExecutor] = None
_executor_shutdown = False


def _get_executor() -> ThreadPoolExecutor:
    global _executor, _executor_shutdown
    if _executor is None or _executor_shutdown:
        _executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="mock-fen")
        _executor_shutdown = False
    return _executor


def _shutdown_executor() -> None:
    """Wait for in-flight deliveries to finish (graceful shutdown)."""
    global _executor_shutdown
    if _executor is not None:
        _executor.shutdown(wait=True)
        _executor_shutdown = True

# Optional OpenAI-compatible LLM judge (any provider; DeepSeek by example).
_llm_config = LLMConfig()

_LLM_SYSTEM = (
    "You are a strict validator for a community data-governance layer. "
    "Review the candidate record for factual quality and cultural sensitivity. "
    "Reply with exactly one word: validated, disputed, or rejected."
)


def _reviewer_recommendation(candidate: dict) -> str:
    """Decision-SUPPORT only (ADR-004): the LLM judge may *recommend* an
    outcome for the DAO to consider — it never votes, never renders a
    governance verdict and never writes gfen:validationStatus. The
    deterministic rule below stands in for the simulated DAO quorum when no
    LLM is configured (demo keeps working without an API key). Generic —
    works for any dataset payload, not just linguistic entities.
    """
    if _llm_config.enabled:
        answer = chat_completion(
            _llm_config,
            _LLM_SYSTEM,
            json.dumps(candidate, ensure_ascii=False),
        )
        recommendation = parse_outcome(answer, ("validated", "disputed", "rejected"))
        if recommendation:
            MOCK_LLM_JUDGE_CALLS.labels(outcome="success").inc()
            logger.info(
                "LLM judge (decision-support, ADR-004) recommends %r for %s",
                recommendation,
                candidate.get("annotation_id"),
            )
            return recommendation
        MOCK_LLM_JUDGE_CALLS.labels(outcome="fallback").inc()
        logger.warning(
            "LLM judge unavailable/indecisive for %s; falling back to rule",
            candidate.get("annotation_id"),
        )
    # Simulated DAO quorum rule (stands in for real Quadratic Voting).
    # Replace only this branch when wiring up a real DAO backend (ADR-002).
    return "validated" if candidate.get("entity_label") else "rejected"


def _fake_decide(candidate: dict) -> dict:
    decision_seq = next(_decision_counter)
    reputation_seq = next(_reputation_counter)
    # The simulated DAO quorum adopts the reviewer recommendation as the
    # governance verdict (quorum_reached=True). In production the verdict
    # always comes from the real community DAO (external, ADR-002) — the
    # LLM never decides (ADR-004).
    outcome = _reviewer_recommendation(candidate)
    logger.info(
        "simulated DAO quorum adopted %r for %s",
        outcome,
        candidate.get("annotation_id"),
    )
    return {
        "annotation_id": candidate["annotation_id"],
        "document_id": candidate.get("document_id"),
        "decision_id": f"g{decision_seq:05d}",
        "outcome": outcome,
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
    start = time.perf_counter()
    for attempt in range(WEBHOOK_MAX_RETRIES):
        try:
            resp = requests.post(WEBHOOK_URL, json=decision, timeout=10)
            resp.raise_for_status()
            MOCK_DELIVERY_SECONDS.observe(time.perf_counter() - start)
            MOCK_DECISIONS_DELIVERED.inc()
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
    MOCK_DELIVERY_FAILURES.inc()


@app.post("/candidates")
def submit_candidates(payload: dict):
    candidates = payload.get("candidates", [])
    for candidate in candidates:
        _get_executor().submit(_deliver_decision_after_delay, candidate)
    MOCK_CANDIDATES_ACCEPTED.inc(len(candidates))
    return {"accepted": len(candidates)}


@app.get("/healthz")
def healthz():
    return {"status": "ok", "note": "this is a DEMO stand-in for FEN's real DAO — see ADR-002"}


@app.get("/readyz")
def readyz():
    """Readiness: the mock depends on nothing external, so it is ready as
    soon as the process serves requests. Its only outbound dependency — the
    FEN Bridge webhook — is probed at delivery time (with retries), not at
    startup, so it must not gate readiness.
    """
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    """Prometheus metrics in text exposition format
    (services/common/metrics.py)."""
    return metrics_response()
