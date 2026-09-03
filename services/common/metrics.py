"""Prometheus metrics shared by the FEN services.

Every HTTP service exposes ``GET /metrics`` in the Prometheus text exposition
format (``prometheus_client.generate_latest``). The consumer processes
(fen-bridge-outbound, validation-consumer) expose the same format on a
dedicated ``METRICS_PORT`` via ``prometheus_client.start_http_server`` (see
their ``main()``), so every service in the stack is scrapable — the local
stack ships Prometheus + Grafana (docker-compose.yml, monitoring/).

Metric naming follows the Prometheus convention: ``fen_<service>_<name>``.
"""
from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# ---- FEN Bridge — inbound webhook -----------------------------------------
WEBHOOK_DECISIONS_RECEIVED = Counter(
    "fen_webhook_decisions_received_total",
    "Governance decisions accepted by the webhook (HTTP 202) and published to Kafka",
)
WEBHOOK_VALIDATION_FAILURES = Counter(
    "fen_webhook_validation_failures_total",
    "Webhook payloads rejected with HTTP 422 (schema validation failure)",
)
WEBHOOK_AUTH_REJECTIONS = Counter(
    "fen_webhook_auth_rejections_total",
    "Webhook requests rejected with HTTP 401 (missing or invalid bearer token)",
)

# ---- mock FEN API (demo DAO stand-in — see ADR-002) -----------------------
MOCK_CANDIDATES_ACCEPTED = Counter(
    "fen_mock_candidates_accepted_total",
    "Entity candidates accepted by the mock FEN API on POST /candidates",
)
MOCK_DECISIONS_DELIVERED = Counter(
    "fen_mock_decisions_delivered_total",
    "Mock governance decisions successfully delivered to the FEN Bridge webhook",
)
MOCK_DELIVERY_FAILURES = Counter(
    "fen_mock_delivery_failures_total",
    "Mock governance decisions that failed to deliver after all webhook retries",
)
MOCK_LLM_JUDGE_CALLS = Counter(
    "fen_mock_llm_judge_calls_total",
    "LLM judge calls made by the mock FEN API, by outcome (success = LLM decided, fallback = rule used)",
    ["outcome"],
)
MOCK_DELIVERY_SECONDS = Histogram(
    "fen_mock_delivery_duration_seconds",
    "Time from candidate submission to webhook delivery (incl. configured decision delay and retries)",
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
)

# ---- Kafka consumers (metrics served on METRICS_PORT) ---------------------
# Both consumer processes (fen-bridge-outbound, validation-consumer) emit
# these names, so the series MUST carry a `process` label — otherwise the
# Grafana dashboard plots two colliding series under one legend
# (TECH-DEBT P2). The value is the consumer group id at inc() time.
KAFKA_MESSAGES_PROCESSED = Counter(
    "fen_kafka_messages_processed_total",
    "Kafka messages fully processed and committed by the consumer processes",
    ["process"],
)
KAFKA_MESSAGES_FAILED = Counter(
    "fen_kafka_messages_failed_total",
    "Kafka messages that failed processing and were left uncommitted (redelivered)",
    ["process"],
)


def metrics_response():
    """Build a FastAPI ``Response`` with the current metric values in the
    Prometheus text exposition format — the body of every ``GET /metrics``.

    ``fastapi`` is imported lazily so consumer processes (fen-bridge-outbound,
    validation-consumer) can import this module without shipping a web
    framework in their images.
    """
    from fastapi import Response  # noqa: PLC0415 - HTTP-only dependency

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
