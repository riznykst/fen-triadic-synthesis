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

import logging
import os
import sys
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.status_api.config import StatusApiConfig  # noqa: E402

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

# gfen: predicate IRI -> response key (short, stable contract)
_PREDICATE_KEYS = {
    "https://w3id.org/got/fen/ontology#validationStatus": "validation_status",
    "https://w3id.org/got/fen/ontology#validationMethod": "validation_method",
    "https://w3id.org/got/fen/ontology#governanceDecisionId": "governance_decision_id",
    "https://w3id.org/got/fen/ontology#reputationSnapshot": "reputation_snapshot",
    "https://w3id.org/got/fen/ontology#ledgerAnchor": "ledger_anchor",
}


def _annotation_uri(annotation_id: str) -> str:
    # Same fragment pattern as sparql_updater._annotation_uri (MVP);
    # production resolves via the GoTriple KG URI scheme (D2.2 section 4.5).
    return f"urn:graphia:annotation:{annotation_id}"


def _fragment(uri: str) -> str:
    return uri.rsplit("#", 1)[-1]


def _query_sparql(annotation_id: str) -> dict:
    """SELECT ?p ?o for the annotation across all named graphs.

    Returns the SPARQL JSON results payload. Raises requests.RequestException
    when the store is unreachable.
    """
    query = (
        "SELECT ?p ?o WHERE { GRAPH ?g { "
        f"<{_annotation_uri(annotation_id)}> ?p ?o "
        "} }"
    )
    resp = requests.post(
        _config.sparql_query_endpoint,
        data={"query": query},
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()


@app.get("/api/v1/status/{annotation_id}")
def get_status(annotation_id: str):
    """Return governance provenance for an annotation, or 404 if the
    annotation is unknown to the store (e.g. never extracted / still
    pending without any gfen: triples).
    """
    try:
        data = _query_sparql(annotation_id)
    except Exception:  # noqa: BLE001 - any store failure -> 503, never 500
        logger.exception("SPARQL endpoint %s unreachable", _config.sparql_query_endpoint)
        raise HTTPException(status_code=503, detail="RDF store unavailable")

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


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    try:
        resp = requests.get(
            _config.sparql_query_endpoint.replace("/query", "/$/ping"), timeout=5.0
        )
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
