"""Tests for the observability layer: JSON structured logging, Prometheus
/metrics endpoints, readiness probes, and graceful-shutdown plumbing.

All offline — TestClient with fakes, mocked HTTP for the mock's delivery
path, and NO real signal emulation (the loops' signal handlers are only ever
registered inside ``main()``, which these tests never call).
"""
from __future__ import annotations

import json
import logging
from unittest import mock

import requests
from fastapi.testclient import TestClient

from mock_fen_api import main as mock_main
from services.common import metrics as metrics_mod
from services.common.logging_config import JsonFormatter, log_level_from_env, setup_logging
from services.fen_bridge.webhook import app as webhook_app

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


def _counter_value(counter, labels=None):
    """Current value of a prometheus_client Counter (plain or labeled)."""
    for metric in counter.collect():
        for sample in metric.samples:
            if labels is None or sample.labels == labels:
                return sample.value
    return 0.0


# ---- structured logging ---------------------------------------------------


def test_json_formatter_emits_valid_json_with_service_field():
    formatter = JsonFormatter("fen-bridge-webhook")
    record = logging.LogRecord(
        name="services.fen_bridge.webhook",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="decision %s accepted",
        args=("g00042",),
        exc_info=None,
    )
    parsed = json.loads(formatter.format(record))
    assert parsed["service"] == "fen-bridge-webhook"
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "decision g00042 accepted"
    assert parsed["timestamp"]


def test_setup_logging_emits_json_lines_with_extras(capsys):
    logger = setup_logging("test-service", level=logging.DEBUG)
    logger.info("hello", extra={"annotation_id": "a1"})
    out = capsys.readouterr().out
    parsed = json.loads(out.strip().splitlines()[-1])
    assert parsed["service"] == "test-service"
    assert parsed["message"] == "hello"
    assert parsed["annotation_id"] == "a1"


def test_log_level_from_env(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    assert log_level_from_env() == logging.DEBUG
    monkeypatch.delenv("LOG_LEVEL")
    assert log_level_from_env() == logging.INFO
    monkeypatch.setenv("LOG_LEVEL", "BOGUS")
    assert log_level_from_env() == logging.INFO


# ---- /metrics and /readyz (webhook) ---------------------------------------


def test_webhook_metrics_endpoint_returns_200_with_key_metrics():
    client = TestClient(webhook_app)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    body = resp.text
    assert "fen_webhook_decisions_received_total" in body
    assert "fen_webhook_validation_failures_total" in body
    assert "fen_webhook_auth_rejections_total" in body


def test_webhook_readyz_ok_with_fake_producer():
    class _FakeProducer:
        pass

    webhook_app.state.producer = _FakeProducer()
    resp = TestClient(webhook_app).get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_webhook_readyz_reflects_kafka_connection():
    class _DisconnectedProducer:
        def bootstrap_connected(self):
            return False

    webhook_app.state.producer = _DisconnectedProducer()
    resp = TestClient(webhook_app).get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "degraded"
    assert resp.json()["kafka"] == "unreachable"


def test_webhook_counters_increment_on_acceptance_and_errors():
    class _FakeProducer:
        def __init__(self):
            self.sent = []

        def send(self, topic, value=None, key=None):
            self.sent.append((topic, value))

    webhook_app.state.producer = _FakeProducer()
    webhook_app.state.webhook_token = None
    client = TestClient(webhook_app)

    before_ok = _counter_value(metrics_mod.WEBHOOK_DECISIONS_RECEIVED)
    assert client.post("/webhook/decision", json=VALID_DECISION).status_code == 202
    assert _counter_value(metrics_mod.WEBHOOK_DECISIONS_RECEIVED) == before_ok + 1

    before_422 = _counter_value(metrics_mod.WEBHOOK_VALIDATION_FAILURES)
    assert client.post("/webhook/decision", json={"annotation_id": "x"}).status_code == 422
    assert _counter_value(metrics_mod.WEBHOOK_VALIDATION_FAILURES) == before_422 + 1

    webhook_app.state.webhook_token = "s3cret"
    before_401 = _counter_value(metrics_mod.WEBHOOK_AUTH_REJECTIONS)
    assert client.post("/webhook/decision", json=VALID_DECISION).status_code == 401
    assert _counter_value(metrics_mod.WEBHOOK_AUTH_REJECTIONS) == before_401 + 1


# ---- /metrics and /readyz (mock FEN API) ----------------------------------


def test_mock_metrics_endpoint_returns_200_with_key_metrics():
    client = TestClient(mock_main.app)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    assert "fen_mock_candidates_accepted_total" in body
    assert "fen_mock_decisions_delivered_total" in body
    assert "fen_mock_delivery_failures_total" in body
    assert "fen_mock_llm_judge_calls_total" in body
    assert "fen_mock_delivery_duration_seconds" in body


def test_mock_readyz_ok():
    resp = TestClient(mock_main.app).get("/readyz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_mock_candidates_accepted_counter():
    class _NoopExecutor:
        def submit(self, fn, *args, **kwargs):
            return None

    before = _counter_value(metrics_mod.MOCK_CANDIDATES_ACCEPTED)
    with mock.patch.object(mock_main, "_get_executor", return_value=_NoopExecutor()):
        client = TestClient(mock_main.app)
        resp = client.post("/candidates", json={"candidates": [{"annotation_id": "a1"}, {"annotation_id": "a2"}]})
    assert resp.status_code == 200
    assert resp.json()["accepted"] == 2
    assert _counter_value(metrics_mod.MOCK_CANDIDATES_ACCEPTED) == before + 2


def test_mock_delivery_counters_track_success_and_failure():
    before_ok = _counter_value(metrics_mod.MOCK_DECISIONS_DELIVERED)
    with mock.patch.object(mock_main, "DECISION_DELAY_S", 0.0), mock.patch(
        "mock_fen_api.main.requests.post"
    ) as fake_post:
        fake_post.return_value.status_code = 202
        fake_post.return_value.raise_for_status = lambda: None
        mock_main._deliver_decision_after_delay({"annotation_id": "a1", "entity_label": "x"})
    assert _counter_value(metrics_mod.MOCK_DECISIONS_DELIVERED) == before_ok + 1

    before_fail = _counter_value(metrics_mod.MOCK_DELIVERY_FAILURES)
    with mock.patch.object(mock_main, "DECISION_DELAY_S", 0.0), mock.patch.object(
        mock_main, "WEBHOOK_MAX_RETRIES", 1
    ), mock.patch(
        "mock_fen_api.main.requests.post", side_effect=requests.RequestException("boom")
    ):
        mock_main._deliver_decision_after_delay({"annotation_id": "a2", "entity_label": "x"})
    assert _counter_value(metrics_mod.MOCK_DELIVERY_FAILURES) == before_fail + 1


def test_mock_llm_judge_counters_success_and_fallback():
    before_success = _counter_value(metrics_mod.MOCK_LLM_JUDGE_CALLS, {"outcome": "success"})
    with mock.patch.object(
        type(mock_main._llm_config), "enabled", new_callable=mock.PropertyMock, return_value=True
    ), mock.patch.object(mock_main, "chat_completion", return_value="validated"):
        outcome = mock_main._decide_outcome({"annotation_id": "a1", "entity_label": "x"})
    assert outcome == "validated"
    assert _counter_value(metrics_mod.MOCK_LLM_JUDGE_CALLS, {"outcome": "success"}) == before_success + 1

    before_fallback = _counter_value(metrics_mod.MOCK_LLM_JUDGE_CALLS, {"outcome": "fallback"})
    with mock.patch.object(
        type(mock_main._llm_config), "enabled", new_callable=mock.PropertyMock, return_value=True
    ), mock.patch.object(mock_main, "chat_completion", return_value=None):
        outcome = mock_main._decide_outcome({"annotation_id": "a1", "entity_label": "x"})
    assert outcome == "validated"  # deterministic rule fallback
    assert _counter_value(metrics_mod.MOCK_LLM_JUDGE_CALLS, {"outcome": "fallback"}) == before_fallback + 1


# ---- graceful shutdown plumbing (import/module parts only, no signals) ----


def test_graceful_shutdown_helpers_exist_and_pool_is_recreatable():
    """The loops expose their shutdown plumbing without registering any
    signal handlers (that happens only inside ``main()``, never at import),
    and the mock's delivery pool can be shut down gracefully and re-created.
    """
    from services.fen_bridge import outbound
    from services.validation_consumer import main as vc

    assert callable(outbound._install_signal_handlers)
    assert callable(vc._install_signal_handlers)

    assert mock_main._get_executor() is not None
    mock_main._shutdown_executor()
    assert mock_main._executor_shutdown is True
    assert mock_main._get_executor() is not None  # re-created, not bricked
