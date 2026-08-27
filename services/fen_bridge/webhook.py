"""FEN Bridge — inbound webhook.

Receives GovernanceDecision callbacks from the external FEN system (real DAO
in production, mock_fen_api/ for local dev/demo) and publishes them onto
fen.governance.decisions.v1 for the Validation Result Consumer to pick up.

Runs as the `fen-bridge-webhook` container (see docker-compose.yml).
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import ValidationError

from services.common.messages import GovernanceDecision
from services.fen_bridge.config import FenBridgeConfig
from services.fen_bridge.kafka_io import make_producer, send

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="FEN Bridge — inbound webhook")

_config = FenBridgeConfig.from_env()
_producer = None  # lazily created — tests inject their own via app.state


def get_producer():
    global _producer
    if _producer is None:
        _producer = make_producer(_config.kafka_bootstrap_servers)
    return _producer


@app.post("/webhook/decision", status_code=status.HTTP_202_ACCEPTED)
def receive_decision(request: Request, payload: dict):
    """Bearer-token check when FEN_WEBHOOK_TOKEN is configured. Open when
    unset (local dev) — in any non-local deployment a token MUST be set,
    otherwise anyone could forge a DAO decision and overwrite
    gfen:validationStatus.
    """
    token = getattr(app.state, "webhook_token", None) or _config.webhook_token
    if token:
        auth = request.headers.get("Authorization")
        if auth != f"Bearer {token}":
            raise HTTPException(status_code=401, detail="missing or invalid bearer token")

    """Accepts a raw dict, validates it as a GovernanceDecision, and
    publishes it. Returns 422 on a malformed payload rather than silently
    dropping it — this is the one point in the pipeline where we DO want a
    loud failure, since a decision that fails to reach Kafka would silently
    strand an entity in gfen:pending forever.
    """
    try:
        decision = GovernanceDecision.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    producer = app.state.producer if hasattr(app.state, "producer") else get_producer()
    send(producer, _config.topic_governance_decisions, decision.model_dump())
    return {"status": "accepted", "annotation_id": decision.annotation_id}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
