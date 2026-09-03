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

from services.common.logging_config import log_level_from_env, setup_logging
from services.common.messages import GovernanceDecision
from services.common.metrics import (
    WEBHOOK_AUTH_REJECTIONS,
    WEBHOOK_DECISIONS_RECEIVED,
    WEBHOOK_VALIDATION_FAILURES,
    metrics_response,
)
from services.fen_bridge.config import FenBridgeConfig
from services.fen_bridge.kafka_io import make_producer, send

setup_logging("fen-bridge-webhook", level=log_level_from_env())
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
    """Accept a raw decision dict and publish it to Kafka.

    - Bearer-token check first when FEN_WEBHOOK_TOKEN is configured; open
      when unset (local dev) — in any non-local deployment a token MUST be
      set, otherwise anyone could forge a DAO decision and overwrite
      gfen:validationStatus.
    - The payload is validated as a GovernanceDecision: returns 422 on a
      malformed payload rather than silently dropping it — this is the one
      point in the pipeline where we DO want a loud failure, since a decision
      that fails to reach Kafka would silently strand an entity in
      gfen:pending forever.
    """
    token = getattr(app.state, "webhook_token", None) or _config.webhook_token
    if token:
        auth = request.headers.get("Authorization")
        if auth != f"Bearer {token}":
            WEBHOOK_AUTH_REJECTIONS.inc()
            raise HTTPException(status_code=401, detail="missing or invalid bearer token")

    try:
        decision = GovernanceDecision.model_validate(payload)
    except ValidationError as exc:
        WEBHOOK_VALIDATION_FAILURES.inc()
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    producer = app.state.producer if hasattr(app.state, "producer") else get_producer()
    send(producer, _config.topic_governance_decisions, decision.model_dump())
    WEBHOOK_DECISIONS_RECEIVED.inc()
    return {"status": "accepted", "annotation_id": decision.annotation_id}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    """Readiness: the webhook is ready once its Kafka producer can publish.
    ``bootstrap_connected`` is a safe metadata-level check that never creates
    topics; test doubles without that method are treated as ready (they
    cannot be probed offline).
    """
    producer = app.state.producer if hasattr(app.state, "producer") else get_producer()
    probe = getattr(producer, "bootstrap_connected", None)
    connected = probe() if callable(probe) else True
    return {
        "status": "ok" if connected else "degraded",
        "kafka": "connected" if connected else "unreachable",
    }


@app.get("/metrics")
def metrics():
    """Prometheus metrics in text exposition format
    (services/common/metrics.py)."""
    return metrics_response()
