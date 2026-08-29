"""Builds the SPARQL DELETE/INSERT that writes gfen: governance provenance
onto an existing oa:Annotation instance, and executes it against a SPARQL
1.1 Update endpoint (Fuseki locally, Virtuoso in production — same
protocol, per ADR-001: only the decision is anchored/written here, never
raw linguistic content, which is untouched in Virtuoso's own named graph).

`build_update_query` is a pure function — test it against an in-memory
rdflib.Graph without any live triple store (see tests/test_sparql_updater.py).
"""
from __future__ import annotations

import logging

import requests

from services.common import gfen_ontology as ns
from services.common.messages import GovernanceDecision
from services.common.pid import w3id_uri

logger = logging.getLogger(__name__)


def _annotation_uri(annotation_id: str) -> str:
    # In production this resolves via the same {domain}/{type}/{concept}/{reference}
    # pattern GoTriple KG uses (D2.2 §4.5); kept as a local fragment here for
    # the MVP so tests don't depend on a specific deployment domain.
    return f"urn:graphia:annotation:{annotation_id}"


def build_update_query(decision: GovernanceDecision, named_graph_uri: str) -> str:
    """Return a SPARQL 1.1 Update string that:

    1. removes any prior gfen:validationStatus/governanceDecisionId/etc.
       triples for this annotation (idempotent — safe to re-apply);
    2. inserts the new status, method, decision/reputation PIDs, and,
       if present, the ledger anchor.

    Everything is scoped to `named_graph_uri`, matching D2.2 §3.5's use of
    named graphs as the unit of update/replace/remove.
    """
    annotation = _annotation_uri(decision.annotation_id)
    status_uri = ns.STATUS_MAP[decision.outcome.value]
    method_uri = ns.METHOD_MAP[decision.method.value]
    decision_uri = w3id_uri("g", int(decision.decision_id.lstrip("g")))
    reputation_uri = w3id_uri("r", int(decision.reputation_snapshot_id.lstrip("r")))

    optional_anchor = ""
    if decision.ledger_anchor:
        optional_anchor = f'  <{annotation}> <{ns.PROP_LEDGER_ANCHOR}> "{decision.ledger_anchor}" .\n'

    return f"""
PREFIX gfen: <{ns.GFEN}>
DELETE {{
  GRAPH <{named_graph_uri}> {{
    <{annotation}> gfen:validationStatus ?oldStatus ;
                   gfen:validationMethod ?oldMethod ;
                   gfen:governanceDecisionId ?oldDecision ;
                   gfen:reputationSnapshot ?oldReputation ;
                   gfen:ledgerAnchor ?oldAnchor .
  }}
}}
INSERT {{
  GRAPH <{named_graph_uri}> {{
    <{annotation}> gfen:validationStatus <{status_uri}> ;
                   gfen:validationMethod <{method_uri}> ;
                   gfen:governanceDecisionId <{decision_uri}> ;
                   gfen:reputationSnapshot <{reputation_uri}> .
{optional_anchor}  }}
}}
WHERE {{
  GRAPH <{named_graph_uri}> {{
    OPTIONAL {{ <{annotation}> gfen:validationStatus ?oldStatus }}
    OPTIONAL {{ <{annotation}> gfen:validationMethod ?oldMethod }}
    OPTIONAL {{ <{annotation}> gfen:governanceDecisionId ?oldDecision }}
    OPTIONAL {{ <{annotation}> gfen:reputationSnapshot ?oldReputation }}
    OPTIONAL {{ <{annotation}> gfen:ledgerAnchor ?oldAnchor }}
  }}
}}
""".strip()


def apply_update(sparql_update_endpoint: str, query: str, timeout_s: float = 10.0, auth=None) -> None:
    """Execute the update against a live SPARQL 1.1 Update endpoint. Raises
    on failure — an update that silently fails to land would leave the
    entity stuck at gfen:pending with no signal, which is worse than a
    loud, retryable error (contrast with FenClient.submit_candidates, which
    deliberately swallows errors for a different reason — see its
    docstring).
    """
    resp = requests.post(
        sparql_update_endpoint,
        data={"update": query},
        timeout=timeout_s,
        auth=auth,
    )
    resp.raise_for_status()
    logger.info("applied governance update to %s", sparql_update_endpoint)
