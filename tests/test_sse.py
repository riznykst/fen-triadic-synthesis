"""Tests for the SSE event bus in the mock FEN API (real-time UI updates)."""
from __future__ import annotations

from unittest import mock

from fastapi.testclient import TestClient

from mock_fen_api import main as mock_main


class _NoopExecutor:
    def submit(self, fn, *args, **kwargs):
        return None


def test_subscribe_broadcast_unsubscribe():
    q = mock_main._subscribe()
    try:
        mock_main._broadcast("vote", {"annotation_id": "a1", "outcome": "validated"})
        payload = q.get_nowait()
        assert payload.startswith("event: vote")
        assert '"a1"' in payload

        mock_main._unsubscribe(q)
        mock_main._broadcast("decision", {"annotation_id": "a1", "outcome": "validated"})
        assert q.empty(), "unsubscribed subscriber must not receive events"
    finally:
        mock_main._unsubscribe(q)


def test_submit_candidates_broadcasts():
    q = mock_main._subscribe()
    try:
        with mock.patch.object(mock_main, "_get_executor", return_value=_NoopExecutor()):
            resp = TestClient(mock_main.app).post(
                "/candidates", json={"candidates": [{"annotation_id": "a1", "entity_label": "x"}]}
            )
        assert resp.status_code == 200
        payload = q.get_nowait()
        assert payload.startswith("event: candidates")
    finally:
        mock_main._unsubscribe(q)


def test_cast_vote_broadcasts(monkeypatch):
    monkeypatch.setattr(mock_main, "VOTING_MODE", "qv")
    q = mock_main._subscribe()
    try:
        client = TestClient(mock_main.app)
        client.post("/candidates", json={"candidates": [{"annotation_id": "a1", "entity_label": "x"}]})
        q.get_nowait()  # consume the candidates event
        client.post("/candidates/a1/vote", json={"outcome": "validated", "intensity": 2, "voter": "v1"})
        payload = q.get_nowait()
        assert payload.startswith("event: vote")
        assert '"reached": false' in payload
    finally:
        mock_main._unsubscribe(q)