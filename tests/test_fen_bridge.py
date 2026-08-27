"""Tests for the FEN Bridge: outbound forwarding and inbound webhook.
All offline — mocked Kafka consumer, mocked HTTP client, TestClient.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from services.fen_bridge.config import FenBridgeConfig
from services.fen_bridge.outbound import run
from services.fen_bridge.webhook import app

VALID_DECISION = {
    "annotation_id": "annotation_a1",
    "document_id": "d12345",
    "decision_id": "g00042",
    "outcome": "validated",
    "method": "quadratic_voting",
    "quorum_reached": True,
    "reputation_snapshot_id": "r00042",
    "ledger_anchor": "0xA1B2C3",
    "decided_at": "2026-08-25T10:14:00Z",
}


class _FakeMessage:
    def __init__(self, value: dict):
        self.value = value


class _FakeConsumer:
    """Minimal stand-in for kafka-python's KafkaConsumer.poll()."""

    def __init__(self, records: dict):
        self._records = records
        self.poll_calls = 0

    def poll(self, timeout_ms=None, max_records=None):
        self.poll_calls += 1
        return self._records


class _FakeClient:
    def __init__(self):
        self.submitted = []

    def submit_candidates(self, batch):
        self.submitted.append(batch)


class _FakeProducer:
    def __init__(self):
        self.sent = []

    def send(self, topic, value):
        self.sent.append((topic, value))


def test_outbound_forwards_batch():
    config = FenBridgeConfig.from_env()
    records = {None: [_FakeMessage({"annotation_id": "a1"}), _FakeMessage({"annotation_id": "a2"})]}
    consumer = _FakeConsumer(records)
    client = _FakeClient()

    run(config, client, consumer)

    assert client.submitted == [[{"annotation_id": "a1"}, {"annotation_id": "a2"}]]


def test_outbound_empty_batch_is_noop():
    config = FenBridgeConfig.from_env()
    consumer = _FakeConsumer({})
    client = _FakeClient()

    run(config, client, consumer)

    assert client.submitted == []


def _webhook_client(token=None):
    """TestClient with a fresh fake producer and explicit webhook token state."""
    producer = _FakeProducer()
    app.state.producer = producer
    app.state.webhook_token = token
    return TestClient(app), producer


def test_webhook_accepts_valid_decision_and_publishes():
    client, producer = _webhook_client(token=None)

    resp = client.post("/webhook/decision", json=VALID_DECISION)

    assert resp.status_code == 202
    assert len(producer.sent) == 1
    topic, value = producer.sent[0]
    assert topic == "fen.governance.decisions.v1"
    assert value["annotation_id"] == "annotation_a1"


def test_webhook_rejects_malformed_payload():
    client, producer = _webhook_client(token=None)

    resp = client.post("/webhook/decision", json={"annotation_id": "x"})

    assert resp.status_code == 422
    assert producer.sent == []


def test_webhook_requires_token_when_configured():
    client, producer = _webhook_client(token="s3cret")

    resp = client.post("/webhook/decision", json=VALID_DECISION)
    assert resp.status_code == 401
    assert producer.sent == []

    resp_ok = client.post(
        "/webhook/decision",
        json=VALID_DECISION,
        headers={"Authorization": "Bearer s3cret"},
    )
    assert resp_ok.status_code == 202
    assert len(producer.sent) == 1
