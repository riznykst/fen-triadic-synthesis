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

import asyncio
import queue
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF

from services.common import gfen_ontology as ns
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
VOTING_MODE = os.getenv("FEN_MOCK_VOTING", "auto")  # "auto" | "community" | "qv"
QUORUM_REQUIRED = int(os.getenv("FEN_MOCK_QUORUM", "3"))     # classic count quorum
QV_THRESHOLD = int(os.getenv("FEN_MOCK_QV_THRESHOLD", "10"))  # QV weighted-score threshold
MAX_INTENSITY = 5                                             # QV intensity cap (cost = i^2)

OUTCOMES = ("validated", "disputed", "rejected")

_decision_counter = itertools.count(1)
_reputation_counter = itertools.count(1)

# In-flight candidate state (UI demo): annotation_id -> record.
_candidates: Dict[str, dict] = {}
_reputation_history: list = []
# Voter/contributor reputation (demo QV mode): name -> points.
_reputation: Dict[str, int] = {}
_state_lock = threading.Lock()

# ---- SSE event bus (real-time UI updates — replaces 3s polling) ------------
_event_subscribers: set = set()
_event_lock = threading.Lock()


def _broadcast(event: str, data: dict) -> None:
    """Fan out an event to all /events subscribers (best-effort, never
    raises — a slow consumer just misses events, the UI re-polls/refreshes)."""
    payload = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    with _event_lock:
        for subscriber in list(_event_subscribers):
            try:
                subscriber.put_nowait(payload)
            except queue.Full:
                pass


def _subscribe():
    subscriber = queue.Queue(maxsize=100)
    with _event_lock:
        _event_subscribers.add(subscriber)
    return subscriber


def _unsubscribe(subscriber) -> None:
    with _event_lock:
        _event_subscribers.discard(subscriber)

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

_SCAFFOLD_SYSTEM = (
    "You are an Agentic Scaffolding layer for a community data-governance "
    "framework (validation overlay for ANY dataset type). Analyse the statement "
    "and return ONLY this JSON (no markdown, no code fences): "
    '{"schema_hints": ["2-3 brief schema guidance notes for structuring this knowledge"], '
    '"relationships": ["1-3 semantic relationships identified in the text"], '
    '"ambiguities": ["any ambiguity or missing context - empty array [] if none"], '
    '"triple": {"subject": "...", "predicate": "...", "object": "...", "context": "...", '
    '"language_or_domain": "...", "evidence_type": "personal_expertise | community_consensus | archival"}}'
)


def _parse_scaffold_json(answer: Optional[str]) -> Optional[dict]:
    """Parse the scaffold agent's JSON answer; tolerate code fences."""
    if not answer:
        return None
    try:
        cleaned = answer.replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned)
        triple = data.get("triple")
        if not isinstance(triple, dict) or not triple.get("subject"):
            return None
        return {
            "schema_hints": data.get("schema_hints", []),
            "relationships": data.get("relationships", []),
            "ambiguities": data.get("ambiguities", []),
            "triple": triple,
            "source": "llm",
        }
    except (json.JSONDecodeError, TypeError):
        return None


# ------------------------------------------------------------------ voting
def majority_outcome(votes: Dict[str, int]) -> str:
    """Deterministic majority: highest count, ties broken by OUTCOMES order."""
    return max(OUTCOMES, key=lambda o: (votes.get(o, 0), -OUTCOMES.index(o)))


def quorum_total(votes: Dict[str, int]) -> int:
    return sum(votes.values())


# ----------------------------------------------------------------------- QV
def qv_cost(intensity: int) -> int:
    """Quadratic cost: a vote with weight ``intensity`` spends intensity^2
    credits (capture-resistance; the cost curve is not the participation
    driver — ADR-005)."""
    return intensity * intensity


def qv_scores(qv_votes: list, delegations: Optional[Dict[str, str]] = None) -> Dict[str, int]:
    """Weighted scores per outcome from QV votes (each vote carries an
    ``intensity`` weight). One voter may vote at most once per proposal —
    enforced in cast_vote (ADR-005 distinct-identity hint); scores weigh by
    intensity.

    Liquid democracy (ADR-005 decision 2): a voter who has NOT voted on the
    proposal but has delegated to a voter who did contributes one extra
    weight to the delegate's chosen outcome."""
    scores = {o: 0 for o in OUTCOMES}
    voted = set()
    for vote in qv_votes:
        voted.add(vote.get("voter"))
        scores[vote["outcome"]] += int(vote.get("intensity", 1))
    if delegations:
        for voter, delegate in delegations.items():
            if voter in voted or voter == delegate:
                continue
            for vote in qv_votes:
                if vote.get("voter") == delegate:
                    scores[vote["outcome"]] += 1
                    break
    return scores


def qv_decide(scores: Dict[str, int], threshold: int) -> Optional[str]:
    """Outcome whose weighted score reached the threshold; ties broken by
    OUTCOMES order. Returns None while the proposal is still open."""
    best = max(OUTCOMES, key=lambda o: (scores[o], -OUTCOMES.index(o)))
    return best if scores[best] >= threshold else None


def _record_candidate(candidate: dict) -> None:
    annotation_id = candidate["annotation_id"]
    with _state_lock:
        if annotation_id not in _candidates:
            # LLM/rule recommendation computed ONCE at submission, display-only
            # (ADR-004: the LLM recommends, the community decides; it never
            # votes and its suggestion is not part of the quorum).
            recommendation = _reviewer_recommendation(candidate)
            _candidates[annotation_id] = {
                "annotation_id": annotation_id,
                "document_id": candidate.get("document_id"),
                "entity_label": candidate.get("entity_label"),
                "status": "pending",
                "votes": {"validated": 0, "disputed": 0, "rejected": 0},
                "qv_votes": [],
                "qv_voters": set(),
                "delegations": {},
                "llm_recommendation": recommendation,
                "candidate": dict(candidate),
                "decision": None,
            }


def _set_status(annotation_id: str, status: str, decision: Optional[dict] = None) -> None:
    with _state_lock:
        if annotation_id in _candidates:
            _candidates[annotation_id]["status"] = status
            if decision is not None:
                _candidates[annotation_id]["decision"] = decision


def _apply_reputation(annotation_id: str, outcome: str) -> None:
    """Demo reputation (ADR-005 incentives): ONLY an approved (validated)
    entry rewards its contributor (+2) and the voters of the winning outcome
    (+1). Rejected/disputed proposals award nothing — incentives must not
    reward failed outcomes. Classic-mode votes carry no voter names, so only
    QV-mode votes contribute."""
    if outcome != "validated":
        return
    with _state_lock:
        record = _candidates.get(annotation_id)
        if record is None:
            return
        submitter = record.get("candidate", {}).get("submitter") or "contributor_1"
        _reputation[submitter] = _reputation.get(submitter, 0) + 2
        _reputation_history.append({
            "at": datetime.now(timezone.utc).isoformat(),
            "annotation_id": annotation_id,
            "actor": submitter,
            "delta": 2,
            "reason": "contributor: validated",
        })
        for vote in record.get("qv_votes", []):
            if vote.get("outcome") == outcome and vote.get("voter"):
                voter = vote["voter"]
                _reputation[voter] = _reputation.get(voter, 0) + 1
                _reputation_history.append({
                    "at": datetime.now(timezone.utc).isoformat(),
                    "annotation_id": annotation_id,
                    "actor": voter,
                    "delta": 1,
                    "reason": f"voter: {outcome}",
                })


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
                "llm_recommendation": record.get("llm_recommendation"),
                "quorum": {
                    "votes": quorum_total(record["votes"]),
                    "required": QUORUM_REQUIRED,
                    "reached": quorum_total(record["votes"]) >= QUORUM_REQUIRED,
                },
                "qv": {
                    "votes": list(record["qv_votes"]),
                    "scores": qv_scores(record["qv_votes"], record["delegations"]),
                    "delegations": dict(record["delegations"]),
                    "threshold": QV_THRESHOLD,
                    "reached": qv_decide(qv_scores(record["qv_votes"], record["delegations"]), QV_THRESHOLD) is not None,
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


def _fake_decide(
    candidate: dict, outcome: Optional[str] = None, recommendation: Optional[str] = None
) -> dict:
    """Build a GovernanceDecision-shaped payload. When ``outcome`` is None
    the simulated DAO quorum adopts the reviewer recommendation (auto mode);
    ``recommendation`` may carry the one computed at submission time to avoid
    a second LLM call (ADR-004: recommendation is display-only anyway).
    """
    decision_seq = next(_decision_counter)
    reputation_seq = next(_reputation_counter)
    if outcome is None:
        outcome = recommendation or _reviewer_recommendation(candidate)
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


def _deliver_decision_after_delay(
    candidate: dict, forced_outcome: Optional[str] = None, recommendation: Optional[str] = None
) -> None:
    """Wait the configured delay, then deliver the decision to the webhook
    with a few retries. A lost demo decision is logged, not fatal.
    """
    time.sleep(DECISION_DELAY_S)
    decision = _fake_decide(candidate, outcome=forced_outcome, recommendation=recommendation)
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
            _apply_reputation(candidate["annotation_id"], decision["outcome"])
            _broadcast("decision", {"annotation_id": candidate["annotation_id"], "outcome": decision["outcome"]})
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


def _ontology_match(triple: dict) -> list:
    """Agent 2 — Ontology Matcher (demo): look the triple's subject/object up
    in the mock's in-memory registry (stand-in for a SPARQL lookup against
    the existing knowledge graph). Returns known candidates with matching
    labels."""
    labels = {str(triple.get("subject", "")).lower(), str(triple.get("object", "")).lower()}
    matches = []
    with _state_lock:
        for rec in _candidates.values():
            label = str(rec.get("entity_label") or "").lower()
            if label and label in labels:
                matches.append({
                    "annotation_id": rec["annotation_id"],
                    "entity_label": rec.get("entity_label"),
                    "status": rec["status"],
                })
    return matches


def _disambiguate(triple: dict) -> list:
    """Agent 3 — Disambiguator: propose external identifiers. Uses the LLM
    (decision-support, ADR-004) when configured; otherwise returns an empty
    list (the demo keeps working offline)."""
    if not _llm_config.enabled:
        return []
    answer = chat_completion(
        _llm_config,
        "You are a knowledge-graph disambiguator. For the given triple, reply "
        "with a JSON array of external identifiers, each "
        '{"type": "wikidata"|"geonames"|"getty", "value": "<id>", "label": "<short label>"}. '
        "Reply with [] if nothing applies. JSON only.",
        json.dumps(triple, ensure_ascii=False),
    )
    if not answer:
        return []
    try:
        parsed = json.loads(answer)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)][:5]
    except json.JSONDecodeError:
        logger.warning("disambiguator returned non-JSON; ignoring")
    return []


def _shacl_validate_scaffold(triple: dict) -> dict:
    """Validate a scaffolded triple against gfen:ScaffoldedTripleShape
    (docs/ontology/fen-shapes.ttl) BEFORE it goes to voting. Returns
    ``{valid, violations}``. Never raises — validation failures are data,
    not errors (the UI shows them to the contributor). Falls back to
    ``valid: None`` when pyshacl is unavailable."""
    try:
        from pyshacl import validate  # lazy: pyshacl is a demo-time dependency

        graph = Graph()
        node = URIRef("urn:fen:scaffold:triple")
        graph.add((node, RDF.type, URIRef(ns.SCAFFOLDED_TRIPLE)))
        for field, prop_uri in (
            ("subject", ns.PROP_SUBJECT),
            ("predicate", ns.PROP_PREDICATE),
            ("object", ns.PROP_OBJECT),
            ("language_or_domain", ns.PROP_LANGUAGE_OR_DOMAIN),
        ):
            value = triple.get(field)
            if value:
                graph.add((node, URIRef(prop_uri), Literal(str(value))))
        shapes_path = Path(__file__).resolve().parents[1] / "docs" / "ontology" / "fen-shapes.ttl"
        conforms, results_graph, _ = validate(graph, shacl_graph=str(shapes_path))
        violations = []
        if not conforms:
            for _s, pred, obj in results_graph:
                if str(pred).endswith("resultMessage"):
                    violations.append(str(obj))
        return {"valid": bool(conforms), "violations": violations[:5]}
    except Exception as exc:  # noqa: BLE001 - validation is advisory in the demo
        logger.warning("SHACL validation unavailable (%s)", exc)
        return {"valid": None, "violations": [], "error": str(exc)}


# ------------------------------------------------------------------- routes
@app.post("/candidates")
def submit_candidates(payload: dict):
    candidates = payload.get("candidates", [])
    for candidate in candidates:
        _record_candidate(candidate)
        if VOTING_MODE in ("community", "qv"):
            # UI demo modes: wait for votes (POST .../vote).
            logger.info("candidate %s queued for %s voting", candidate["annotation_id"], VOTING_MODE)
        else:
            with _state_lock:
                rec = _candidates.get(candidate["annotation_id"])
                recommendation = rec.get("llm_recommendation") if rec else None
            _get_executor().submit(
                _deliver_decision_after_delay, candidate, None, recommendation
            )
    MOCK_CANDIDATES_ACCEPTED.inc(len(candidates))
    _broadcast("candidates", {"accepted": len(candidates)})
    return {"accepted": len(candidates)}


@app.get("/candidates")
def list_candidates():
    """All in-flight candidates with vote/quorum/QV state + reputation,
    reputation history (ADR-005 incentives) and LLM-judge accuracy over the
    decided ones (recommendation vs community outcome — ADR-004 display-only
    quality signal)."""
    candidates = _public_state()
    with _state_lock:
        reputation = dict(_reputation)
        history = list(reversed(_reputation_history[-50:]))
    decided = [c for c in candidates if c.get("decision")]
    agreements = sum(
        1 for c in decided
        if c.get("llm_recommendation") and c["llm_recommendation"] == c["decision"].get("outcome")
    )
    return {
        "candidates": candidates,
        "mode": VOTING_MODE,
        "qv_threshold": QV_THRESHOLD,
        "reputation": reputation,
        "reputation_history": history,
        "llm_accuracy": {
            "agreements": agreements,
            "total": len(decided),
            "accuracy": (agreements / len(decided)) if decided else None,
        },
    }


@app.post("/candidates/{annotation_id}/vote")
def cast_vote(annotation_id: str, payload: dict):
    """Cast one vote. Two demo modes (web/api.md):

    - ``community`` (classic): one vote per call; quorum = vote count
      (``FEN_MOCK_QUORUM``), outcome = majority.
    - ``qv`` (Quadratic Voting): vote carries an optional ``intensity``
      (1..5, default 1, cost = intensity^2) and optional ``voter``/
      ``comment``; the proposal is decided when an outcome weighted score
      reaches ``FEN_MOCK_QV_THRESHOLD`` (default 10).

    When decided, the outcome is delivered once (claim inside the lock, so a
    concurrent vote sees status != pending and gets 409).
    """
    outcome = payload.get("outcome")
    if outcome not in OUTCOMES:
        raise HTTPException(status_code=422, detail=f"outcome must be one of {OUTCOMES}")

    try:
        intensity = int(payload.get("intensity", 1))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"intensity must be an integer 1..{MAX_INTENSITY}")
    if not 1 <= intensity <= MAX_INTENSITY:
        raise HTTPException(status_code=422, detail=f"intensity must be 1..{MAX_INTENSITY}")

    with _state_lock:
        record = _candidates.get(annotation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="unknown annotation_id")
        if record["status"] != "pending":
            raise HTTPException(status_code=409, detail=f"candidate already decided: {record['status']}")
        if VOTING_MODE not in ("community", "qv"):
            raise HTTPException(status_code=409, detail="voting is disabled (FEN_MOCK_VOTING=auto)")

        if VOTING_MODE == "qv":
            voter = payload.get("voter") or f"validator_{len(record['qv_votes']) + 1}"
            if voter in record["qv_voters"]:
                # ADR-005 distinct-identity hint: one person, one vote.
                raise HTTPException(
                    status_code=409,
                    detail=f"voter {voter} has already voted on this proposal",
                )
            record["qv_voters"].add(voter)
            record["qv_votes"].append({
                "outcome": outcome,
                "intensity": intensity,
                "voter": voter,
                "comment": payload.get("comment") or "",
            })
            scores = qv_scores(record["qv_votes"], record["delegations"])
            reached = qv_decide(scores, QV_THRESHOLD) is not None
            final = qv_decide(scores, QV_THRESHOLD) if reached else None
        else:
            record["votes"][outcome] += 1
            scores = None
            total = quorum_total(record["votes"])
            reached = total >= QUORUM_REQUIRED
            final = majority_outcome(record["votes"]) if reached else None

        votes = dict(record["votes"])
        if reached:
            record["status"] = "deciding"

    _broadcast("vote", {"annotation_id": annotation_id, "outcome": outcome, "reached": reached})

    if reached:
        _get_executor().submit(_deliver_decision_after_delay, {"annotation_id": annotation_id}, final)
        return {
            "annotation_id": annotation_id,
            "votes": votes,
            "qv": {
                "votes": list(record["qv_votes"]),
                "scores": scores,
                "threshold": QV_THRESHOLD,
            },
            "quorum": {"votes": quorum_total(votes), "required": QUORUM_REQUIRED, "reached": True},
            "cost": qv_cost(intensity) if VOTING_MODE == "qv" else 1,
            "outcome": final,
            "note": "decision threshold reached — decision being delivered",
        }
    return {
        "annotation_id": annotation_id,
        "votes": votes,
        "qv": {
            "votes": list(record["qv_votes"]),
            "scores": scores,
            "threshold": QV_THRESHOLD,
        },
        "quorum": {"votes": quorum_total(votes), "required": QUORUM_REQUIRED, "reached": False},
        "cost": qv_cost(intensity) if VOTING_MODE == "qv" else 1,
    }


@app.post("/candidates/{annotation_id}/delegate")
def delegate_vote(annotation_id: str, payload: dict):
    """Liquid democracy (ADR-005 decision 2): a voter who has NOT voted yet
    on this proposal can delegate their weight to another voter. Delegated
    weight follows the delegate's outcome choice in qv_scores. One active
    delegation per voter per proposal (re-delegation replaces it)."""
    voter = (payload.get("voter") or "").strip()
    delegate = (payload.get("delegate") or "").strip()
    if not voter or not delegate:
        raise HTTPException(status_code=422, detail="voter and delegate are required")
    if voter == delegate:
        raise HTTPException(status_code=422, detail="cannot delegate to yourself")
    with _state_lock:
        record = _candidates.get(annotation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="unknown annotation_id")
        if record["status"] != "pending":
            raise HTTPException(status_code=409, detail=f"candidate already decided: {record['status']}")
        if VOTING_MODE != "qv":
            raise HTTPException(status_code=409, detail="delegation is a QV-mode feature (FEN_MOCK_VOTING=qv)")
        if voter in {v.get("voter") for v in record["qv_votes"]}:
            raise HTTPException(status_code=409, detail=f"voter {voter} has already voted — no delegation")
        record["delegations"][voter] = delegate
    _broadcast("vote", {"annotation_id": annotation_id, "delegation": True, "voter": voter})
    return {
        "annotation_id": annotation_id,
        "delegations": dict(record["delegations"]),
        "note": f"{voter} delegates to {delegate}",
    }


@app.post("/scaffold")
def scaffold(payload: dict):
    """Agentic Scaffolding (Phase 1) — decision-support only (ADR-004).

    Uses the configured OpenAI-compatible LLM (FEN_LLM_*) to structure a
    natural-language statement into a semantic triple with schema hints,
    relationships and ambiguity flags. Generic — works for ANY dataset type
    (framework, not language-specific). Falls back to a deterministic rule
    when no LLM is configured, so the demo works offline.
    """
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is required")

    if _llm_config.enabled:
        answer = chat_completion(_llm_config, _SCAFFOLD_SYSTEM, text)
        parsed = _parse_scaffold_json(answer)
        if parsed:
            parsed["shacl"] = _shacl_validate_scaffold(parsed.get("triple", {}))
            parsed["agents"] = {
                "extractor": "llm",
                "matcher": _ontology_match(parsed.get("triple", {})),
                "disambiguator": _disambiguate(parsed.get("triple", {})),
            }
            return parsed
        logger.warning("scaffold agent unavailable/indecisive; using rule fallback")

    snippet = text[:48]
    response = {
        "schema_hints": ["rule-based fallback (no LLM configured) — the triple is a rough split"],
        "relationships": [],
        "ambiguities": [],
        "triple": {
            "subject": snippet,
            "predicate": "mentions",
            "object": text[-48:] if len(text) > 96 else snippet,
            "context": "",
            "language_or_domain": "und",
            "evidence_type": "community_consensus",
        },
        "source": "rule_fallback",
    }
    response["shacl"] = _shacl_validate_scaffold(response["triple"])
    response["agents"] = {
        "extractor": "rule",
        "matcher": _ontology_match(response["triple"]),
        "disambiguator": [],
    }
    return response


@app.get("/events")
async def events():
    """Server-Sent Events stream: candidates/vote/decision updates for the
    portal and triadic views (replaces 3s polling)."""
    subscriber = _subscribe()

    async def stream():
        try:
            yield "event: ready\ndata: {}\n\n"
            while True:
                try:
                    yield subscriber.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(1)
        finally:
            _unsubscribe(subscriber)

    return StreamingResponse(stream(), media_type="text/event-stream")


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
