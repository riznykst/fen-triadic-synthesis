"""FEN Status API — read-side web service (web-interface layer).

Provides:
- GET /api/v1/status/{annotation_id} — governance provenance for one
  annotation, resolved live from the RDF store via SPARQL (Fuseki locally,
  Virtuoso in production). This is the data source for the Flow 2 status
  widget (<fen-status>).
- /web — the web interface itself (widget demo + DAO portal) served as
  static files (zero-build: plain JS/HTML, no toolchain required).

CORS is enabled so the widget can be embedded in third-party pages
(GoTriple, dataset portals). Never writes to the graph — this service is
read-only (query endpoint only; see ADR-001: writes belong exclusively to
the Validation Result Consumer).
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Callable, Optional

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from rdflib import Graph, Literal, URIRef

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.status_api.config import StatusApiConfig  # noqa: E402
from services.common import gfen_ontology as ns  # noqa: E402
from services.common.graph_uris import annotation_uri  # noqa: E402
from services.common.metrics import metrics_response  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="FEN Status API — read-side web service")

_config = StatusApiConfig.from_env()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_config.cors_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# gfen: predicate IRI -> response key (short, stable contract). IRIs come
# from services.common.gfen_ontology (TECH-DEBT P1 — single source, no
# copy-pasted literals that can drift from the ontology module).
# TODO(ADR-006): add gfen:challengeWindowEnd -> "challenge_window_end" ONLY
# once ADR-006 is accepted — the ontology predicate is "proposed, not yet
# applied" and nothing writes it today; exposing it now would fake data.
_PREDICATE_KEYS = {
    ns.PROP_VALIDATION_STATUS: "validation_status",
    ns.PROP_VALIDATION_METHOD: "validation_method",
    ns.PROP_GOVERNANCE_DECISION_ID: "governance_decision_id",
    ns.PROP_REPUTATION_SNAPSHOT: "reputation_snapshot",
    ns.PROP_LEDGER_ANCHOR: "ledger_anchor",
}


def _fragment(uri: str) -> str:
    return uri.rsplit("#", 1)[-1]


EXPORT_FORMATS = {
    "ttl": ("text/turtle", "turtle"),
    "turtle": ("text/turtle", "turtle"),
    "jsonld": ("application/ld+json", "json-ld"),
    "nt": ("application/n-triples", "nt"),
}


def _sparql_to_graph(data: dict, annotation_id: str) -> Graph:
    """Turn SPARQL SELECT bindings into an rdflib Graph (annotation subject,
    predicate URIs, URI/literal objects as reported by the store)."""
    graph = Graph()
    subject = URIRef(annotation_uri(annotation_id))
    for binding in data.get("results", {}).get("bindings", []):
        predicate = binding.get("p", {}).get("value", "")
        value = binding.get("o", {}).get("value", "")
        kind = binding.get("o", {}).get("type", "literal")
        if not predicate:
            continue
        obj = URIRef(value) if kind == "uri" else Literal(value)
        graph.add((subject, URIRef(predicate), obj))
    return graph


def _ro_crate(annotation_id: str, data: dict) -> dict:
    """A simplified RO-Crate (v1.1) packaging of one governance record:
    the annotation node plus the gfen: provenance properties. JSON-LD —
    the same shape the widget reads, wrapped in the crate structure."""
    bindings = data.get("results", {}).get("bindings", [])
    props = {}
    for binding in bindings:
        key = _PREDICATE_KEYS.get(binding.get("p", {}).get("value", ""))
        if key is None:
            continue
        value = binding.get("o", {}).get("value", "")
        kind = binding.get("o", {}).get("type", "literal")
        props[key] = _fragment(value) if kind == "uri" and key == "validation_status" else value
    annotation = annotation_uri(annotation_id)
    return {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "ro-crate-metadata.json",
                "@type": "CreativeWork",
                "about": {"@id": "./"},
                "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
            },
            {"@id": "./", "@type": "Dataset", "name": f"FEN governance record: {annotation_id}"},
            {"@id": annotation, "@type": "oa:Annotation", **props},
        ],
    }


def _query_sparql(annotation_id: str) -> dict:
    """SELECT ?p ?o for the annotation across all named graphs.

    Returns the SPARQL JSON results payload. Raises requests.RequestException
    when the store is unreachable.
    """
    query = (
        "SELECT ?p ?o WHERE { GRAPH ?g { "
        f"<{annotation_uri(annotation_id)}> ?p ?o "
        "} }"
    )
    resp = requests.post(
        _config.sparql_query_endpoint,
        data={"query": query},
        timeout=_config.sparql_timeout_s,
    )
    resp.raise_for_status()
    return resp.json()


def _status_payload(annotation_id: str, data: dict) -> dict:
    """Build the /api/v1/status/{id} response body from SPARQL bindings.

    Single source of truth for the record shape: the REST endpoint and the
    SSE stream (GET /api/v1/events/{id}) both call this, so an SSE event
    payload is byte-for-byte the REST JSON body (widgets render both paths
    identically, and records that do not exist yet are seen as they appear).
    """
    bindings = data.get("results", {}).get("bindings", [])
    if not bindings:
        return {
            "annotation_id": annotation_id,
            "found": False,
            "validation_status": "unknown",
        }

    result = {"annotation_id": annotation_id, "found": True, "provenance": []}
    for binding in bindings:
        predicate = binding.get("p", {}).get("value", "")
        value = binding.get("o", {}).get("value", "")
        kind = binding.get("o", {}).get("type", "literal")
        key = _PREDICATE_KEYS.get(predicate)
        if key is None:
            continue
        if kind == "uri":
            result[key] = _fragment(value) if key == "validation_status" else value
        else:
            result[key] = value
        result["provenance"].append({"predicate": predicate, "value": value, "type": kind})
    result.setdefault("validation_status", "unknown")
    return result


def _sse_frame(event: str, data: dict) -> str:
    """One SSE frame: ``event: <name>\\ndata: <json>\\n\\n``. Compact JSON
    separators match starlette's JSONResponse, keeping event payloads
    byte-identical to the REST endpoint body."""
    return "event: {}\ndata: {}\n\n".format(
        event,
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
    )


async def _status_stream(
    annotation_id: str,
    poller: Callable[[], dict],
    interval_s: float,
    heartbeat_s: float,
    stop_after: Optional[int] = None,
):
    """Async generator of SSE frames for ONE connected client.

    - First tick fires immediately: the client learns the current record
      right away (or ``found: false`` when the store has nothing yet).
    - Then polls ``poller()`` every ``interval_s`` seconds and emits
      ``event: status`` ONLY when the payload changed since the last poll
      (canonical JSON comparison) — the widget never re-renders on noise.
    - ``poller`` is injectable so tests can feed canned payloads; it raises
      ``requests.RequestException`` when the store is unreachable (same
      contract as ``_query_sparql``) -> ``event: error`` and retry on the
      next tick (the stream itself never closes; EventSource reconnects
      anyway if a proxy drops it).
    - ``: ping`` heartbeat comments every ``heartbeat_s`` keep idle
      connections alive through proxies.
    - ``stop_after`` bounds the number of poll ticks so tests terminate
      deterministically (production passes None = stream forever).
    """
    last_canonical: Optional[str] = None
    ticks = 0
    next_poll = 0.0  # first tick is immediate
    next_heartbeat = heartbeat_s
    while stop_after is None or ticks < stop_after:
        now = time.monotonic()
        if now >= next_poll:
            next_poll = now + interval_s
            ticks += 1
            try:
                payload = _status_payload(annotation_id, poller())
                canonical = json.dumps(payload, sort_keys=True)
                if canonical != last_canonical:
                    last_canonical = canonical
                    yield _sse_frame("status", payload)
            except Exception:  # noqa: BLE001 - store down: error frame, keep polling
                logger.exception("SSE poll failed for %s", annotation_id)
                yield _sse_frame("error", {"annotation_id": annotation_id, "error": "RDF store unavailable"})
        if now >= next_heartbeat:
            next_heartbeat = now + heartbeat_s
            yield ": ping\n\n"
        await asyncio.sleep(min(0.1, interval_s / 4))


@app.get("/api/v1/status/{annotation_id}")
def get_status(annotation_id: str):
    """Return governance provenance for an annotation, or 404 if the
    annotation is unknown to the store (e.g. never extracted / still
    pending without any gfen: triples).
    """
    try:
        data = _query_sparql(annotation_id)
    except Exception as exc:  # noqa: BLE001 - any store failure -> 503, never 500
        logger.exception("SPARQL endpoint %s unreachable", _config.sparql_query_endpoint)
        raise HTTPException(status_code=503, detail="RDF store unavailable") from exc

    return _status_payload(annotation_id, data)


@app.get("/api/v1/events/{annotation_id}")
async def status_events(annotation_id: str):
    """Server-Sent Events: live governance status for one annotation
    (read-only, ADR-001).

    Why status-api polls the RDF store instead of consuming Kafka: this
    service is strictly read-side — no consumer group, no writes. The store
    is the source of truth for read models; a Kafka-fed event bus is a
    future production option (out of scope here).

    Frames (same contract as the widget, see web/api.md §4b):
      event: status  — payload is byte-for-byte the GET /api/v1/status/{id}
                       body; emitted on connect and on every CHANGED record
      event: error   — RDF store unreachable; retried on the next poll tick
      : ping         — heartbeat comment (keeps idle connections alive)
    """
    async def stream():
        async for frame in _status_stream(
            annotation_id,
            lambda: _query_sparql(annotation_id),
            _config.sse_poll_interval_s,
            _config.sse_heartbeat_s,
        ):
            yield frame

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/api/v1/export/{annotation_id}")
def export_annotation(annotation_id: str, format: str = "ttl"):
    """Export one annotation's governance provenance as RDF (TTL, JSON-LD,
    N-Triples) or as an RO-Crate (format=crate). Read-only (ADR-001);
    503 when the store is unreachable, 404 when there is no record yet.
    """
    try:
        data = _query_sparql(annotation_id)
    except Exception as exc:  # noqa: BLE001 - any store failure -> 503, never 500
        logger.exception("SPARQL endpoint %s unreachable", _config.sparql_query_endpoint)
        raise HTTPException(status_code=503, detail="RDF store unavailable") from exc

    if format == "crate":
        crate = _ro_crate(annotation_id, data)
        return JSONResponse(content=crate)

    entry = EXPORT_FORMATS.get(format.lower())
    if entry is None:
        raise HTTPException(
            status_code=422,
            detail=f"format must be one of {sorted(EXPORT_FORMATS)} or 'crate'",
        )
    mime, rdflib_format = entry
    graph = _sparql_to_graph(data, annotation_id)
    if len(graph) == 0:
        raise HTTPException(status_code=404, detail="no governance record for this annotation")
    body = graph.serialize(format=rdflib_format)
    return Response(content=body, media_type=mime)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    """Prometheus metrics (services/common/metrics.py) — scraped by the
    local prometheus service (monitoring/prometheus/prometheus.yml)."""
    return metrics_response()


@app.get("/readyz")
def readyz():
    try:
        resp = requests.get(_config.sparql_ping_endpoint, timeout=_config.sparql_ping_timeout_s)
        resp.raise_for_status()
        return {"status": "ok", "sparql": "reachable"}
    except Exception:  # noqa: BLE001 - any probe failure -> degraded
        return {"status": "degraded", "sparql": "unreachable"}


# Static web interface (zero-build: plain HTML/JS, no toolchain).
_web_dir = Path(__file__).resolve().parents[2] / _config.web_dir
if _web_dir.is_dir():
    app.mount("/web", StaticFiles(directory=str(_web_dir)), name="web")
else:
    logger.warning("web dir %s not found — serving /web disabled", _web_dir)
