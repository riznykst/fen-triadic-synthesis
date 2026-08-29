"""Tests for the community-voting demo mode of the mock FEN API."""
from __future__ import annotations

import time
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from mock_fen_api import main as mock_main


@pytest.fixture(autouse=True)
def _clean_state():
    with mock_main._state_lock:
        mock_main._candidates.clear()
    yield
    with mock_main._state_lock:
        mock_main._candidates.clear()


def _client():
    return TestClient(mock_main.app)


def _ok_post(*args, **kwargs):
    resp = mock.Mock()
    resp.raise_for_status = lambda: None
    return resp


class _NoopExecutor:
    """Replaces the real ThreadPoolExecutor so no background thread ever
    performs a real network call during tests (all-offline guarantee)."""

    def submit(self, fn, *args, **kwargs):
        return None


def test_majority_outcome_and_quorum_total():
    assert mock_main.majority_outcome({"validated": 2, "disputed": 1, "rejected": 0}) == "validated"
    assert mock_main.majority_outcome({"validated": 1, "disputed": 2, "rejected": 0}) == "disputed"
    # tie broken deterministically by OUTCOMES order
    assert mock_main.majority_outcome({"validated": 1, "disputed": 1, "rejected": 1}) == "validated"
    assert mock_main.quorum_total({"validated": 2, "disputed": 1}) == 3


def test_candidates_list_in_auto_mode():
    client = _client()
    with mock.patch.object(mock_main, "_get_executor", return_value=_NoopExecutor()):
        resp = client.post("/candidates", json={"candidates": [{"annotation_id": "a1", "entity_label": "x"}]})
    assert resp.json() == {"accepted": 1}
    listed = client.get("/candidates").json()["candidates"]
    assert len(listed) == 1
    assert listed[0]["status"] == "pending"
    assert listed[0]["quorum"]["required"] == mock_main.QUORUM_REQUIRED
    # decision-support recommendation is computed once and exposed (ADR-004)
    assert listed[0]["llm_recommendation"] == "validated"


def test_vote_rejected_in_auto_mode():
    client = _client()
    with mock.patch.object(mock_main, "_get_executor", return_value=_NoopExecutor()):
        client.post("/candidates", json={"candidates": [{"annotation_id": "a1", "entity_label": "x"}]})
    resp = client.post("/candidates/a1/vote", json={"outcome": "validated"})
    assert resp.status_code == 409


def test_vote_unknown_candidate_404():
    resp = _client().post("/candidates/nope/vote", json={"outcome": "validated"})
    assert resp.status_code == 404


def test_vote_invalid_outcome_422():
    resp = _client().post("/candidates/a1/vote", json={"outcome": "maybe"})
    assert resp.status_code == 422


def test_community_voting_reaches_quorum_and_delivers(monkeypatch):
    monkeypatch.setattr(mock_main, "VOTING_MODE", "community")
    monkeypatch.setattr(mock_main, "QUORUM_REQUIRED", 2)
    monkeypatch.setattr(mock_main, "DECISION_DELAY_S", 0.0)
    monkeypatch.setattr(mock_main, "WEBHOOK_MAX_RETRIES", 1)
    # Keep requests.post patched for the WHOLE test: the async delivery runs
    # in a real executor thread AFTER the vote calls, so a with-block patch
    # would be gone by then and the thread would hit the real network.
    monkeypatch.setattr(mock_main.requests, "post", _ok_post)
    client = _client()
    client.post("/candidates", json={"candidates": [{"annotation_id": "a1", "entity_label": "x"}]})

    r1 = client.post("/candidates/a1/vote", json={"outcome": "validated"})
    assert r1.status_code == 200
    assert r1.json()["quorum"]["reached"] is False

    r2 = client.post("/candidates/a1/vote", json={"outcome": "disputed"})
    assert r2.status_code == 200
    assert r2.json()["outcome"] == "validated"  # majority: validated 1 vs disputed 1 -> tie -> validated

    # wait for the async delivery to land
    for _ in range(50):
        with mock_main._state_lock:
            rec = dict(mock_main._candidates.get("a1", {}))
        if rec.get("status") == "deciding":
            time.sleep(0.05)
            continue
        break
    assert rec.get("status") == "validated"
    assert rec.get("decision", {}).get("outcome") == "validated"
    assert rec["decision"]["quorum_reached"] is True
