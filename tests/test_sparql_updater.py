from datetime import datetime, timezone

from rdflib import Dataset, Namespace, URIRef

from services.common.messages import GovernanceDecision, ValidationMethod, ValidationStatus
from services.validation_consumer.sparql_updater import _annotation_uri, build_update_query

GFEN = Namespace("https://w3id.org/got/fen/ontology#")
NAMED_GRAPH = "urn:graphia:document:d12345:graph"


def _decision(**overrides) -> GovernanceDecision:
    base = dict(
        annotation_id="annotation_a1",
        document_id="d12345",
        decision_id="g00042",
        outcome=ValidationStatus.validated,
        method=ValidationMethod.quadratic_voting,
        quorum_reached=True,
        reputation_snapshot_id="r00042",
        ledger_anchor="0xA1B2C3",
        decided_at=datetime(2026, 8, 25, 10, 14, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return GovernanceDecision(**base)


def _graph_with_seed_annotation() -> Dataset:
    """An in-memory dataset (multi-graph, needed for GRAPH <...> queries)
    pre-loaded with an oa:Annotation as it would look right after WP4
    extraction — status pending, no governance properties yet — mirroring
    the 'before' state in examples/sample-validation-flow.ttl.
    """
    ds = Dataset()
    annotation = URIRef(_annotation_uri("annotation_a1"))
    ds.add((annotation, GFEN.validationStatus, GFEN.pending, URIRef(NAMED_GRAPH)))
    return ds


def _named(ds: Dataset):
    """The specific named graph the update writes to — queries must go
    through this, not the dataset's default graph."""
    return ds.graph(URIRef(NAMED_GRAPH))


def test_build_update_query_is_valid_sparql_and_applies_cleanly():
    ds = _graph_with_seed_annotation()
    decision = _decision()
    query = build_update_query(decision, NAMED_GRAPH)

    ds.update(query)  # raises on malformed SPARQL — this IS the syntax check

    annotation = URIRef(_annotation_uri("annotation_a1"))
    g = _named(ds)

    statuses = list(g.triples((annotation, GFEN.validationStatus, None)))
    assert statuses == [(annotation, GFEN.validationStatus, GFEN.validated)], (
        "expected exactly one, updated validationStatus triple"
    )

    methods = list(g.triples((annotation, GFEN.validationMethod, None)))
    assert methods == [(annotation, GFEN.validationMethod, GFEN.QuadraticVoting)]

    decision_ids = list(g.triples((annotation, GFEN.governanceDecisionId, None)))
    assert str(decision_ids[0][2]) == "https://w3id.org/fen/id/decision/g00042"

    anchors = list(g.triples((annotation, GFEN.ledgerAnchor, None)))
    assert str(anchors[0][2]) == "0xA1B2C3"


def test_build_update_query_is_idempotent_on_reapply():
    ds = _graph_with_seed_annotation()
    decision = _decision()
    query = build_update_query(decision, NAMED_GRAPH)

    ds.update(query)
    ds.update(query)  # apply twice — must not duplicate triples

    annotation = URIRef(_annotation_uri("annotation_a1"))
    statuses = list(_named(ds).triples((annotation, GFEN.validationStatus, None)))
    assert len(statuses) == 1, "re-applying the same decision must not create duplicate triples"


def test_build_update_query_without_ledger_anchor_omits_the_triple():
    ds = _graph_with_seed_annotation()
    decision = _decision(ledger_anchor=None)
    query = build_update_query(decision, NAMED_GRAPH)

    ds.update(query)

    annotation = URIRef(_annotation_uri("annotation_a1"))
    anchors = list(_named(ds).triples((annotation, GFEN.ledgerAnchor, None)))
    assert anchors == []


def test_build_update_query_reflects_rejected_outcome():
    ds = _graph_with_seed_annotation()
    decision = _decision(outcome=ValidationStatus.rejected, ledger_anchor=None)
    query = build_update_query(decision, NAMED_GRAPH)

    ds.update(query)

    annotation = URIRef(_annotation_uri("annotation_a1"))
    statuses = list(_named(ds).triples((annotation, GFEN.validationStatus, None)))
    assert statuses == [(annotation, GFEN.validationStatus, GFEN.rejected)]
