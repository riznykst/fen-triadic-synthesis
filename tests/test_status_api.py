"""Tests for the Status API (read-side web service, services/status_api).

All offline: the SPARQL and ping HTTP calls are mocked.
"""
from __future__ import annotations

import asyncio
import json
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


# ----------------------------------------------------- SSE events (live status)
# The stream generator is BOUNDED in tests: never call
# TestClient(app).get("/api/v1/events/...") with the real infinite generator
# (it hangs) — iterate `_status_stream` directly with `asyncio.run()`.


def _collect_sse(annotation_id, poller, interval_s=0.01, heartbeat_s=0.05, stop_after=1):
    """Run the stream generator to completion (bounded by stop_after) and
    return the raw frames."""
    async def _run():
        frames = []
        async for frame in status_main._status_stream(
            annotation_id, poller, interval_s, heartbeat_s, stop_after=stop_after
        ):
            frames.append(frame)
        return frames

    return asyncio.run(_run())


def _sse_payload(frame: str) -> dict:
    return json.loads(frame.split("data: ", 1)[1])


def _sse_events(frames):
    """Frames split into (event_name, data) for the typed events (ignores
    heartbeat `: ping` comments)."""
    out = []
    for f in frames:
        if f.startswith("event: "):
            name = f.split("\n", 1)[0].replace("event: ", "")
            out.append((name, _sse_payload(f)))
    return out


def test_sse_first_event_is_byte_identical_to_rest_payload():
    bindings = [
        _binding(GFEN + "validationStatus", GFEN + "validated"),
        _binding(GFEN + "validationMethod", GFEN + "QuadraticVoting"),
        _binding(GFEN + "ledgerAnchor", "0xA1B2", "literal"),
    ]
    frames = _collect_sse("annotation_a1", lambda: {"results": {"bindings": bindings}})
    events = _sse_events(frames)
    assert len(events) == 1
    assert events[0][0] == "status"

    with mock.patch.object(status_main.requests, "post", _sparql_ok(bindings)):
        rest = TestClient(status_main.app).get("/api/v1/status/annotation_a1").json()
    # same shape AND same serialization as the REST endpoint
    assert events[0][1] == rest
    assert json.dumps(events[0][1], ensure_ascii=False, separators=(",", ":")) == \
        json.dumps(rest, ensure_ascii=False, separators=(",", ":"))


def test_sse_unknown_record_reported_found_false():
    frames = _collect_sse("annotation_x", lambda: {"results": {"bindings": []}})
    events = _sse_events(frames)
    assert events[0][1] == {
        "annotation_id": "annotation_x",
        "found": False,
        "validation_status": "unknown",
    }


def test_sse_pushes_only_changed_payloads():
    calls = {"n": 0}

    def poller():
        calls["n"] += 1
        if calls["n"] <= 2:
            return {"results": {"bindings": []}}  # unknown
        return {"results": {"bindings": [_binding(GFEN + "validationStatus", GFEN + "validated")]}}

    frames = _collect_sse("annotation_a1", poller, stop_after=5)
    events = _sse_events(frames)
    statuses = [p for (name, p) in events if name == "status"]
    # tick1: unknown (change vs nothing) -> event; tick2: same -> NO event;
    # tick3: validated (change) -> event; ticks 4-5: same -> no events.
    assert [p["validation_status"] for p in statuses] == ["unknown", "validated"]


def test_sse_error_event_when_store_unreachable_and_retries():
    def poller():
        raise requests.RequestException("boom")

    frames = _collect_sse("annotation_a1", poller, stop_after=3)
    events = _sse_events(frames)
    assert [name for (name, _p) in events] == ["error", "error", "error"]
    assert events[0][1]["error"] == "RDF store unavailable"
    assert events[0][1]["annotation_id"] == "annotation_a1"


def test_sse_stream_terminates_after_stop_after():
    # The test completing proves the generator is bounded (no hang).
    assert _collect_sse("annotation_a1", lambda: {"results": {"bindings": []}}, stop_after=0) == []
    frames = _collect_sse("annotation_a1", lambda: {"results": {"bindings": []}}, stop_after=3)
    # dedup: 3 ticks with an identical payload collapse into ONE status frame
    assert len(_sse_events(frames)) == 1
    assert _sse_events(frames)[0][1]["validation_status"] == "unknown"


def test_sse_heartbeat_comments_are_emitted():
    frames = _collect_sse(
        "annotation_a1", lambda: {"results": {"bindings": []}}, interval_s=0.01, heartbeat_s=0.03, stop_after=20
    )
    assert any(f.startswith(": ping") for f in frames)


def test_sse_endpoint_headers():
    # Direct call (no TestClient): the response object is created but the
    # stream is never iterated, so this cannot hang on the infinite
    # generator. Iterating the generator is covered by the bounded tests
    # above — TestClient().get() on this endpoint would hang by design.
    resp = asyncio.run(status_main.status_events("annotation_x"))
    assert resp.media_type == "text/event-stream"
    assert resp.headers["cache-control"] == "no-cache"