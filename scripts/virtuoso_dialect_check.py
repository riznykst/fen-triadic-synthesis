"""SPARQL 1.1 dialect check against a LIVE OpenLink Virtuoso — the engine of
the GoTriple KG (GRAPHIA's production store). Fuseki is not enough: Virtuoso
has its own dialect quirks, so this script applies the real
``build_update_query`` twice (idempotency) and SELECTs the triples back from
the named graph.

Usage:
    docker compose --profile virtuoso up -d virtuoso
    python scripts/virtuoso_dialect_check.py

Env (defaults for the compose service above):
    VIRTUOSO_ENDPOINT   http://localhost:8890
    VIRTUOSO_USER       dba
    VIRTUOSO_PASSWORD   dba

Exits 0 on success; non-zero with a clear message otherwise. This is an
integration check — NOT part of the offline pytest suite (the CI e2e job
runs it when the virtuoso profile is available).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.auth import HTTPDigestAuth

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.common.messages import GovernanceDecision, ValidationMethod, ValidationStatus  # noqa: E402
from services.validation_consumer.sparql_updater import build_update_query  # noqa: E402

ENDPOINT = os.getenv("VIRTUOSO_ENDPOINT", "http://localhost:8890").rstrip("/")
UPDATE_URL = ENDPOINT + "/sparql-auth"   # unauthenticated /sparql is read-only in Virtuoso
QUERY_URL = ENDPOINT + "/sparql"
AUTH = (os.getenv("VIRTUOSO_USER", "dba"), os.getenv("VIRTUOSO_PASSWORD", "dba"))

NAMED_GRAPH = "urn:graphia:document:d2026_014:graph"
EXPECTED_TRIPLES = 5  # validationStatus, validationMethod, governanceDecisionId,
                      # reputationSnapshot, ledgerAnchor


def _decision() -> GovernanceDecision:
    return GovernanceDecision(
        annotation_id="annotation_dialect",
        document_id="d2026_014",
        decision_id="g00042",
        outcome=ValidationStatus.validated,
        method=ValidationMethod.quadratic_voting,
        quorum_reached=True,
        reputation_snapshot_id="r00042",
        ledger_anchor="0xDIALECT",
        decided_at=datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
    )


def _apply(query: str) -> None:
    # Virtuoso's /sparql-auth negotiates Digest auth by default; fall back
    # to Basic if the instance allows it.
    for auth in (HTTPDigestAuth(*AUTH), AUTH):
        resp = requests.post(UPDATE_URL, data={"update": query}, auth=auth, timeout=20)
        if resp.status_code != 401:
            break
    if resp.status_code >= 400:
        raise RuntimeError(f"UPDATE failed ({resp.status_code}): {resp.text[:400]}")
    resp.raise_for_status()


def _count() -> int:
    sparql = (
        "SELECT (COUNT(*) AS ?c) WHERE { GRAPH <" + NAMED_GRAPH + "> { ?s ?p ?o } }"
    )
    # Virtuoso serves XML by default — ask for SPARQL JSON explicitly.
    resp = requests.get(
        QUERY_URL,
        params={"query": sparql, "format": "application/sparql-results+json"},
        timeout=20,
    )
    resp.raise_for_status()
    if not resp.text.strip():
        raise RuntimeError("SELECT returned an empty body")
    bindings = resp.json().get("results", {}).get("bindings", [])
    return int(bindings[0]["c"]["value"]) if bindings else 0


def main() -> int:
    decision = _decision()
    query = build_update_query(decision, NAMED_GRAPH)

    print(f"UPDATE endpoint: {UPDATE_URL} (auth={AUTH[0]})")
    print("Applying the update TWICE (idempotency check)...")
    _apply(query)
    _apply(query)

    count = _count()
    print(f"Triples in {NAMED_GRAPH}: {count} (expected {EXPECTED_TRIPLES})")
    if count != EXPECTED_TRIPLES:
        print(f"FAIL: expected exactly {EXPECTED_TRIPLES} triples, got {count}")
        return 1
    print("VIRTUOSO DIALECT CHECK PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
