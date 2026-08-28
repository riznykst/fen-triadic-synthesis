"""Tests that the RDF/SHACL artefacts stay parseable and complete."""
from __future__ import annotations

from rdflib import Graph, Namespace

SH = "http://www.w3.org/ns/shacl#"


def test_ontology_ttl_parses():
    g = Graph()
    g.parse("docs/ontology/fen-ontology.ttl", format="turtle")
    assert len(g) > 0


def test_shacl_shapes_parse_and_declare_node_shapes():
    g = Graph()
    g.parse("docs/ontology/fen-shapes.ttl", format="turtle")
    assert len(g) > 0
    node_shapes = [s for s, p, o in g if str(o) == SH + "NodeShape"]
    assert len(node_shapes) >= 2, f"expected at least 2 NodeShapes, got {len(node_shapes)}"

OWL = Namespace("http://www.w3.org/2002/07/owl#")
GFEN = Namespace("https://w3id.org/got/fen/ontology#")


def test_ontology_declares_owl_imports_stub():
    g = Graph()
    g.parse("docs/ontology/fen-ontology.ttl", format="turtle")
    imports = list(g.triples((None, OWL.imports, None)))
    assert len(imports) == 1, f"expected exactly one owl:imports, got {len(imports)}"
    subject, _, obj = imports[0]
    assert str(obj).startswith("https://")
    assert str(subject).endswith("ontology#")