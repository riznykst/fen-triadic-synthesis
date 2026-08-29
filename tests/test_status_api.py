"""Tests for the Status API (read-side web service, services/status_api).

All offline: the SPARQL and ping HTTP calls are mocked.
"""
from __future__ import annotations

from unittest import mock

import requests
from fastapi.testclient import TestClient
from rdflib import Graph

from services.status_api import main as status_main

GFEN = "https://w3id.org/got/fen/ontology#"


def _binding(predicate: str, value: str, type_: str = "uri") -> dict:
    return {"p": {"value": predicate}, "o": {"value": value, "type": type_}}


def _sparql_ok(bindings):
    post = mock.Mock()
    post.return_value.status_code = 200
    post.return_value.json.return_value = {"results": {"bindings": bindings}}
    return post


def test_status_unknown_when_no_governance_triples():
    with mock.patch.object(status_main.requests, "post", _sparql_ok([])):
        resp = TestClient(status_main.app).get("/api/v1/status/annotation_x")
    assert resp.status_code == 200
    assert resp.json() == {
        "annotation_id": "annotation_x",
        "found": False,
        "validation_status": "unknown",
    }


def test_status_maps_gfen_properties_and_provenance():
    bindings = [
        _binding(GFEN + "validationStatus", GFEN + "validated"),
        _binding(GFEN + "validationMethod", GFEN + "QuadraticVoting"),
        _binding(GFEN + "governanceDecisionId", "https://w3id.org/fen/id/decision/g00042"),
        _binding(GFEN + "ledgerAnchor", "0xA1B2", "literal"),
        _binding("https://example.org/not-a-fen-predicate", "skip-me"),
    ]
    with mock.patch.object(status_main.requests, "post", _sparql_ok(bindings)):
        resp = TestClient(status_main.app).get("/api/v1/status/annotation_a1")

    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    # URI-valued status is shortened to the fragment (stable contract)
    assert body["validation_status"] == "validated"
    # non-status URIs stay full (dereferenceable PIDs)
    assert body["validation_method"] == GFEN + "QuadraticVoting"
    assert body["governance_decision_id"] == "https://w3id.org/fen/id/decision/g00042"
    assert body["ledger_anchor"] == "0xA1B2"
    # unknown predicates are skipped, known ones land in provenance
    assert len(body["provenance"]) == 4


def test_status_503_when_store_unreachable():
    with mock.patch.object(
        status_main.requests, "post", side_effect=requests.RequestException("boom")
    ):
        resp = TestClient(status_main.app).get("/api/v1/status/annotation_a1")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "RDF store unavailable"


def test_readyz_ok_and_degraded():
    ok = mock.Mock()
    ok.return_value.status_code = 200
    ok.return_value.raise_for_status = lambda: None
    with mock.patch.object(status_main.requests, "get", ok):
        assert TestClient(status_main.app).get("/readyz").json()["status"] == "ok"

    broken = mock.Mock()
    broken.return_value.raise_for_status = lambda: (_ for _ in ()).throw(
        requests.RequestException("down")
    )
    with mock.patch.object(status_main.requests, "get", broken):
        assert TestClient(status_main.app).get("/readyz").json()["status"] == "degraded"


# ------------------------------------------------------------------- export
def _export_bindings():
    return [
        _binding(GFEN + "validationStatus", GFEN + "validated"),
        _binding(GFEN + "validationMethod", GFEN + "QuadraticVoting"),
        _binding(GFEN + "ledgerAnchor", "0xA1B2", "literal"),
    ]


def test_export_ttl():
    with mock.patch.object(status_main.requests, "post", _sparql_ok(_export_bindings())):
        resp = TestClient(status_main.app).get("/api/v1/export/annotation_a1?format=ttl")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/turtle")
    g = Graph()
    g.parse(data=resp.text, format="turtle")
    assert len(g) == 3  # validationStatus + validationMethod + ledgerAnchor


def test_export_jsonld():
    with mock.patch.object(status_main.requests, "post", _sparql_ok(_export_bindings())):
        resp = TestClient(status_main.app).get("/api/v1/export/annotation_a1?format=jsonld")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/ld+json")
    g = Graph()
    g.parse(data=resp.text, format="json-ld")
    assert len(g) == 3


def test_export_ntriples():
    with mock.patch.object(status_main.requests, "post", _sparql_ok(_export_bindings())):
        resp = TestClient(status_main.app).get("/api/v1/export/annotation_a1?format=nt")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/n-triples")
    g = Graph()
    g.parse(data=resp.text, format="nt")
    assert len(g) == 3


def test_export_ro_crate():
    with mock.patch.object(status_main.requests, "post", _sparql_ok(_export_bindings())):
        resp = TestClient(status_main.app).get("/api/v1/export/annotation_a1?format=crate")
    assert resp.status_code == 200
    crate = resp.json()
    assert crate["@context"].startswith("https://w3id.org/ro/crate")
    graph = crate["@graph"]
    assert len(graph) == 3  # metadata + dataset + annotation
    annotation = graph[2]
    assert annotation["validation_status"] == "validated"
    assert annotation["ledger_anchor"] == "0xA1B2"


def test_export_bad_format_422():
    with mock.patch.object(status_main.requests, "post", _sparql_ok(_export_bindings())):
        resp = TestClient(status_main.app).get("/api/v1/export/annotation_a1?format=xml")
    assert resp.status_code == 422


def test_export_unknown_annotation_404():
    with mock.patch.object(status_main.requests, "post", _sparql_ok([])):
        resp = TestClient(status_main.app).get("/api/v1/export/annotation_x?format=ttl")
    assert resp.status_code == 404


def test_export_503_when_store_unreachable():
    with mock.patch.object(
        status_main.requests, "post", side_effect=requests.RequestException("boom")
    ):
        resp = TestClient(status_main.app).get("/api/v1/export/annotation_a1?format=ttl")
    assert resp.status_code == 503