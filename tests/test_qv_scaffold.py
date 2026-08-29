"""Tests for the QV voting mode and the /scaffold endpoint of the mock."""
from __future__ import annotations

import time
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from mock_fen_api import main as mock_main


@pytest.fixture(autouse=True)
def _clean():
    with mock_main._state_lock:
        mock_main._candidates.clear()
        mock_main._reputation.clear()
    yield
    with mock_main._state_lock:
        mock_main._candidates.clear()
        mock_main._reputation.clear()


def _ok_post(*args, **kwargs):
    resp = mock.Mock()
    resp.raise_for_status = lambda: None
    return resp


# ---------------------------------------------------------------- pure QV
def test_qv_cost_is_quadratic():
    assert mock_main.qv_cost(1) == 1
    assert mock_main.qv_cost(2) == 4
    assert mock_main.qv_cost(5) == 25


def test_qv_scores_sum_intensity():
    votes = [
        {"outcome": "validated", "intensity": 3},
        {"outcome": "validated", "intensity": 2},
        {"outcome": "disputed", "intensity": 4},
    ]
    assert mock_main.qv_scores(votes) == {"validated": 5, "disputed": 4, "rejected": 0}


def test_qv_decide_threshold_and_ties():
    scores = {"validated": 6, "disputed": 4, "rejected": 0}
    assert mock_main.qv_decide(scores, 10) is None
    assert mock_main.qv_decide(scores, 5) == "validated"
    # tie broken by OUTCOMES order
    tie = {"validated": 10, "disputed": 10, "rejected": 10}
    assert mock_main.qv_decide(tie, 10) == "validated"


# ------------------------------------------------------------ qv vote flow
def test_qv_vote_flow_reaches_threshold_and_delivers(monkeypatch):
    monkeypatch.setattr(mock_main, "VOTING_MODE", "qv")
    monkeypatch.setattr(mock_main, "QV_THRESHOLD", 10)
    monkeypatch.setattr(mock_main, "DECISION_DELAY_S", 0.0)
    monkeypatch.setattr(mock_main, "WEBHOOK_MAX_RETRIES", 1)
    client = TestClient(mock_main.app)
    client.post("/candidates", json={"candidates": [{"annotation_id": "a1", "entity_label": "x", "submitter": "contrib_1"}]})

    with mock.patch("mock_fen_api.main.requests.post", side_effect=_ok_post):
        r1 = client.post("/candidates/a1/vote", json={"outcome": "validated", "intensity": 3, "voter": "v1", "comment": "solid"})
        assert r1.status_code == 200
        assert r1.json()["qv"]["scores"]["validated"] == 3
        assert r1.json()["cost"] == 9

        r2 = client.post("/candidates/a1/vote", json={"outcome": "validated", "intensity": 4, "voter": "v2"})
        assert r2.status_code == 200
        assert "outcome" not in r2.json()  # 7 < 10 — still open
        assert r2.json()["qv"]["scores"]["validated"] == 7

        r3 = client.post("/candidates/a1/vote", json={"outcome": "validated", "intensity": 3, "voter": "v3"})
        assert r3.status_code == 200
        assert r3.json()["outcome"] == "validated"  # 7+3 = 10 >= 10

        for _ in range(50):
            with mock_main._state_lock:
                rec = dict(mock_main._candidates.get("a1", {}))
            if rec.get("status") != "deciding":
                break
            time.sleep(0.05)
        assert rec.get("status") == "validated"
        assert rec["decision"]["quorum_reached"] is True


def test_qv_vote_intensity_validation(monkeypatch):
    monkeypatch.setattr(mock_main, "VOTING_MODE", "qv")
    client = TestClient(mock_main.app)
    client.post("/candidates", json={"candidates": [{"annotation_id": "a1", "entity_label": "x"}]})
    assert client.post("/candidates/a1/vote", json={"outcome": "validated", "intensity": 0}).status_code == 422
    assert client.post("/candidates/a1/vote", json={"outcome": "validated", "intensity": 6}).status_code == 422
    assert client.post("/candidates/a1/vote", json={"outcome": "validated", "intensity": "x"}).status_code == 422


def test_qv_reputation_awarded_on_decision(monkeypatch):
    monkeypatch.setattr(mock_main, "VOTING_MODE", "qv")
    monkeypatch.setattr(mock_main, "QV_THRESHOLD", 5)
    monkeypatch.setattr(mock_main, "DECISION_DELAY_S", 0.0)
    monkeypatch.setattr(mock_main, "WEBHOOK_MAX_RETRIES", 1)
    client = TestClient(mock_main.app)
    client.post("/candidates", json={"candidates": [{"annotation_id": "a1", "entity_label": "x", "submitter": "contrib_1"}]})
    with mock.patch("mock_fen_api.main.requests.post", side_effect=_ok_post):
        client.post("/candidates/a1/vote", json={"outcome": "validated", "intensity": 3, "voter": "v1"})
        client.post("/candidates/a1/vote", json={"outcome": "validated", "intensity": 2, "voter": "v2"})
        for _ in range(50):
            with mock_main._state_lock:
                rec = dict(mock_main._candidates.get("a1", {}))
            if rec.get("status") != "deciding":
                break
            time.sleep(0.05)
    data = client.get("/candidates").json()
    assert data["mode"] == "qv"
    assert data["reputation"]["contrib_1"] == 2
    assert data["reputation"]["v1"] == 1
    assert data["reputation"]["v2"] == 1
    c1 = data["candidates"][0]
    assert c1["submitter"] == "contrib_1"


def test_candidates_list_preserves_submitter_and_triple():
    client = TestClient(mock_main.app)
    triple = {"subject": "Koshary", "predicate": "marks", "object": "trade route"}
    client.post("/candidates", json={"candidates": [{
        "annotation_id": "a2",
        "entity_label": "Koshary",
        "submitter": "alice",
        "triple": triple,
    }]})
    data = client.get("/candidates").json()
    cand = next(c for c in data["candidates"] if c["annotation_id"] == "a2")
    assert cand["submitter"] == "alice"
    assert cand["triple"] == triple


# ----------------------------------------------------------------- scaffold
def test_scaffold_llm_path(monkeypatch):
    monkeypatch.setattr(mock_main, "_llm_config", mock.Mock(enabled=True))
    agent_json = (
        '{"schema_hints": ["use a noun phrase"], "relationships": ["X relates to Y"], '
        '"ambiguities": [], "triple": {"subject": "Komi river", "predicate": "means", '
        '"object": "yu", "context": "hydronym", "language_or_domain": "Komi", '
        '"evidence_type": "community_consensus"}}'
    )
    with mock.patch.object(mock_main, "chat_completion", return_value=agent_json):
        resp = TestClient(mock_main.app).post("/scaffold", json={"text": "In Komi, 'yu' means river"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "llm"
    assert body["triple"]["subject"] == "Komi river"
    assert body["schema_hints"] == ["use a noun phrase"]


def test_scaffold_llm_failure_falls_back(monkeypatch):
    monkeypatch.setattr(mock_main, "_llm_config", mock.Mock(enabled=True))
    with mock.patch.object(mock_main, "chat_completion", return_value=None):
        resp = TestClient(mock_main.app).post("/scaffold", json={"text": "Some statement about a place"})
    assert resp.status_code == 200
    assert resp.json()["source"] == "rule_fallback"
    assert resp.json()["triple"]["subject"]


def test_scaffold_rule_fallback_without_llm():
    resp = TestClient(mock_main.app).post("/scaffold", json={"text": "The old hill is called Koshary"})
    assert resp.status_code == 200
    assert resp.json()["source"] == "rule_fallback"


def test_scaffold_requires_text():
    resp = TestClient(mock_main.app).post("/scaffold", json={"text": "   "})
    assert resp.status_code == 422
