"""Single source of truth for the ``urn:graphia:`` URI scheme (TECH-DEBT P1).

sparql_updater, validation-consumer and status-api used to build these
fragment strings independently and could drift apart (a production change
to the GoTriple KG URI scheme per D2.2 §4.5 must be made HERE, once).

Local MVP pattern:
    annotation subject:     urn:graphia:annotation:{annotation_id}
    document named graph:   urn:graphia:document:{document_id}:graph
    annotation fallback:    urn:graphia:annotation:{annotation_id}:graph
        (used only when a decision carries no document_id — see
        validation_consumer.main.named_graph_uri)
"""
from __future__ import annotations


def annotation_uri(annotation_id: str) -> str:
    """The oa:Annotation subject URI for a governance record."""
    return f"urn:graphia:annotation:{annotation_id}"


def document_graph_uri(document_id: str) -> str:
    """The named graph a document's governance provenance is written to and
    read from (D2.2 §3.5: named graphs are the unit of update/replace)."""
    return f"urn:graphia:document:{document_id}:graph"


def annotation_graph_uri(annotation_id: str) -> str:
    """Fallback named graph when no document id is known for an annotation."""
    return f"urn:graphia:annotation:{annotation_id}:graph"
