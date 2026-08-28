"""Tests for the Status API (read-side web service)."""
from __future__ import annotations

from unittest import mock

from fastapi.testclient import TestClient
from rdflib import Graph

from services.status_api import main as status_main

GFEN = "https://w3id.org/got/fen/ontology#"
DECISION = "https://w3id.org/fen/id/decision/g00042"
SNAPSHOT = "https://w3id.org/fen/id/reputation-snapshot/r00042"


def _bindings():
    return {
        "results": {
            "bindings": [
                {"p": {"value": GFEN + "validationStatus"}, "o": {"value": GFEN + "validated", "type": "uri"}},
                {"p": {"value": GFEN + "validationMethod"}, "o": {"value": GFEN + "QuadraticVoting", "type": "uri"}},
                {"p": {"value": GFEN + "governanceDecisionId"}, "o": {"value": DECISION, "type": "uri"}},
                {"p": {"value": GFEN + "reputationSnapshot"}, "o": {"value": SNAPSHOT, "type": "uri"}},
                {"p": {"value": GFEN + "ledgerAnchor"}, "o": {"value": "0xA1B2C3", "type": "literal"}},
            ]
        }
    }


def test_status_maps_gfen_provenance():
    with mock.patch("services.status_api.main._query_sparql", return_value=_bindings()):
        resp = TestClient(status_main.app).get("/api/v1/status/annotation_a1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    assert body["validation_status"] == "validated"          # short fragment, not URI
    assert body["validation_method"] == GFEN + "QuadraticVoting"
    assert body["governance_decision_id"] == DECISION        # dereferenceable IRI (ADR-003)
    assert body["ledger_anchor"] == "0xA1B2C3"
    assert len(body["provenance"]) == 5


def test_status_unknown_when_no_triples():
    with mock.patch("services.status_api.main._query_sparql", return_value={"results": {"bindings": []}}):
        resp = TestClient(status_main.app).get("/api/v1/status/annotation_never_seen")
    assert resp.status_code == 200
    assert resp.json()["found"] is False
    assert resp.json()["validation_status"] == "unknown"


def test_status_503_when_store_unreachable():
    with mock.patch("services.status_api.main._query_sparql", side_effect=Exception("boom")):
        resp = TestClient(status_main.app).get("/api/v1/status/annotation_a1")
    assert resp.status_code == 503


def test_status_api_sends_cors_headers():
    with mock.patch("services.status_api.main._query_sparql", return_value={"results": {"bindings": []}}):
        resp = TestClient(status_main.app).get(
        "/api/v1/status/annotation_a1", headers={"Origin": "http://example.com"}
    )
    assert resp.headers.get("access-control-allow-origin") == "*"


def test_readyz_degraded_when_sparql_ping_fails():
    with mock.patch("services.status_api.main.requests.get", side_effect=Exception("no store")):
        resp = TestClient(status_main.app).get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "degraded"


def test_web_static_mount_serves_widget():
    resp = TestClient(status_main.app).get("/web/widget/fen-status-widget.js")
    assert resp.status_code == 200
    assert b"customElements.define" in resp.content
