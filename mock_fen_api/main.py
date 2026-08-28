"""Mock FEN API — stands in for the real Agentic Scaffolding + DAO
Quadratic Voting system, for local development and consortium demos only.

Accepts batches of EntityCandidate on POST /candidates and delivers a
synthetic GovernanceDecision to the FEN Bridge webhook. Two decision modes
(FEN_MOCK_VOTING):

- "auto" (default): after a configurable delay the simulated DAO quorum
  adopts the LLM/rule recommendation (see ADR-004) and the decision is
  delivered.
- "community": the UI-facing demo mode — candidates stay gfen:pending until
  community votes arrive via POST /candidates/{id}/vote; when the quorum
  (FEN_MOCK_QUORUM) is reached, the majority outcome is delivered.

Decision logic (in priority order):
1. If an OpenAI-compatible LLM endpoint is configured (FEN_LLM_BASE_URL —
   OpenAI, DeepSeek, local vLLM/Ollama, or GRAPHIA services such as
   LLM4SSH/Quagga exposing such an API), the LLM *recommends* an outcome.
   Decision-support only (ADR-004): it never votes and never decides.
2. Otherwise a deterministic placeholder rule applies (non-empty
   entity_label -> validated, else rejected).

This MUST NOT be mistaken for real DAO/Quadratic Voting governance, which
lives entirely outside this repository (see ADR-002). The REST contract
served here (see web/api.md) is the same contract the real FEN backend is
expected to implement.

Runs as the `mock-fen-api` container (see docker-compose.yml).
"""
from __future__ import annotations

import itertools
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, Optional

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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

# CORS for the web-interface layer (Flow 1 portal calls this service from a
# browser). Server-to-server callers (FEN Bridge) are unaffected.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("FEN_CORS_ORIGINS", "*").split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

WEBHOOK_URL = os.getenv("FEN_BRIDGE_WEBHOOK_URL", "http://localhost:8101/webhook/decision")
DECISION_DELAY_S = float(os.getenv("MOCK_FEN_DECISION_DELAY_S", "3"))
MAX_WORKERS = int(os.getenv("MOCK_FEN_MAX_WORKERS", "8"))
WEBHOOK_MAX_RETRIES = int(os.getenv("MOCK_FEN_WEBHOOK_RETRIES", "3"))
VOTING_MODE = os.getenv("FEN_MOCK_VOTING", "auto")  # "auto" | "community"
QUORUM_REQUIRED = int(os.getenv("FEN_MOCK_QUORUM", "3"))

OUTCOMES = ("validated", "disputed", "rejected")

_decision_counter = itertools.count(1)
_reputation_counter = itertools.count(1)

# In-flight candidate state (UI demo): annotation_id -> record.
_candidates: Dict[str, dict] = {}
_state_lock = threading.Lock()

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


# ------------------------------------------------------------------ voting
def majority_outcome(votes: Dict[str, int]) -> str:
    """Deterministic majority: highest count, ties broken by OUTCOMES order."""
    return max(OUTCOMES, key=lambda o: (votes.get(o, 0), -OUTCOMES.index(o)))


def quorum_total(votes: Dict[str, int]) -> int:
    return sum(votes.values())


def _record_candidate(candidate: dict) -> None:
    annotation_id = candidate["annotation_id"]
    with _state_lock:
        if annotation_id not in _candidates:
            _candidates[annotation_id] = {
                "annotation_id": annotation_id,
                "document_id": candidate.get("document_id"),
                "entity_label": candidate.get("entity_label"),
                "status": "pending",
                "votes": {"validated": 0, "disputed": 0, "rejected": 0},
                "decision": None,
            }


def _set_status(annotation_id: str, status: str, decision: Optional[dict] = None) -> None:
    with _state_lock:
        if annotation_id in _candidates:
            _candidates[annotation_id]["status"] = status
            if decision is not None:
                _candidates[annotation_id]["decision"] = decision


def _public_state() -> list:
    with _state_lock:
        out = []
        for record in _candidates.values():
            out.append({
                "annotation_id": record["annotation_id"],
                "document_id": record["document_id"],
                "entity_label": record["entity_label"],
                "status": record["status"],
                "votes": dict(record["votes"]),
                "quorum": {
                    "votes": quorum_total(record["votes"]),
                    "required": QUORUM_REQUIRED,
                    "reached": quorum_total(record["votes"]) >= QUORUM_REQUIRED,
                },
                "decision": record["decision"],
            })
        return out


# ------------------------------------------------------------ decision logic
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
        recommendation = parse_outcome(answer, OUTCOMES)
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


def _fake_decide(candidate: dict, outcome: Optional[str] = None) -> dict:
    """Build a GovernanceDecision-shaped payload. When ``outcome`` is None
    the simulated DAO quorum adopts the reviewer recommendation (auto mode).
    """
    decision_seq = next(_decision_counter)
    reputation_seq = next(_reputation_counter)
    if outcome is None:
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


def _deliver_decision_after_delay(candidate: dict, forced_outcome: Optional[str] = None) -> None:
    """Wait the configured delay, then deliver the decision to the webhook
    with a few retries. A lost demo decision is logged, not fatal.
    """
    time.sleep(DECISION_DELAY_S)
    decision = _fake_decide(candidate, outcome=forced_outcome)
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
            _set_status(candidate["annotation_id"], decision["outcome"], decision)
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


# ------------------------------------------------------------------- routes
@app.post("/candidates")
def submit_candidates(payload: dict):
    candidates = payload.get("candidates", [])
    for candidate in candidates:
        _record_candidate(candidate)
        if VOTING_MODE == "community":
            # UI demo mode: wait for community votes (POST .../vote).
            logger.info("candidate %s queued for community voting", candidate["annotation_id"])
        else:
            _get_executor().submit(_deliver_decision_after_delay, candidate)
    MOCK_CANDIDATES_ACCEPTED.inc(len(candidates))
    return {"accepted": len(candidates)}


@app.get("/candidates")
def list_candidates():
    """All in-flight candidates with vote/quorum state (Flow 1 portal)."""
    return {"candidates": _public_state()}


@app.post("/candidates/{annotation_id}/vote")
def cast_vote(annotation_id: str, payload: dict):
    """Cast one community vote (Flow 1 portal). When the quorum is reached
    the majority outcome is delivered as the governance decision.
    """
    outcome = payload.get("outcome")
    if outcome not in OUTCOMES:
        raise HTTPException(status_code=422, detail=f"outcome must be one of {OUTCOMES}")
    with _state_lock:
        record = _candidates.get(annotation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="unknown annotation_id")
        if record["status"] != "pending":
            raise HTTPException(status_code=409, detail=f"candidate already decided: {record['status']}")
        if VOTING_MODE != "community":
            raise HTTPException(status_code=409, detail="community voting is disabled (FEN_MOCK_VOTING=auto)")
        record["votes"][outcome] += 1
        votes = dict(record["votes"])
        total = quorum_total(votes)

    if total >= QUORUM_REQUIRED:
        final = majority_outcome(votes)
        _set_status(annotation_id, "deciding")
        _get_executor().submit(_deliver_decision_after_delay, {"annotation_id": annotation_id}, final)
        return {
            "annotation_id": annotation_id,
            "votes": votes,
            "quorum": {"votes": total, "required": QUORUM_REQUIRED, "reached": True},
            "outcome": final,
            "note": "quorum reached — decision being delivered",
        }
    return {
        "annotation_id": annotation_id,
        "votes": votes,
        "quorum": {"votes": total, "required": QUORUM_REQUIRED, "reached": False},
    }


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
