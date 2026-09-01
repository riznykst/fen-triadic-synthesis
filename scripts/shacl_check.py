"""SHACL validation of the FEN governance shapes — a CI step.

Validates RDF data against docs/ontology/fen-shapes.ttl with pySHACL:

- default (no args): self-check — a minimal *valid* annotation must conform
  and a minimal *invalid* one (missing governanceDecisionId) must report
  violations. Fails if either expectation is wrong.
- ``--graph-file FILE``: validate a Turtle/TriG file (e.g.
  examples/sample-validation-flow.trig).
- ``--endpoint URL --graph URI``: fetch a named graph via SPARQL CONSTRUCT
  and validate it (the live gate; the e2e smoke also runs this in-process).

Exit code 0 = all checked data conforms (or, in self-check mode, the invalid
case reported violations), 1 otherwise.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests
from pyshacl import validate

ROOT = Path(__file__).resolve().parents[1]
SHAPES_PATH = ROOT / "docs" / "ontology" / "fen-shapes.ttl"
ONTOLOGY_PATH = ROOT / "docs" / "ontology" / "fen-ontology.ttl"
GFEN = "https://w3id.org/got/fen/ontology#"
VALID_ANNOTATION = f"""
@prefix gfen: <{GFEN}> .
@prefix oa: <http://www.w3.org/ns/oa#> .

<urn:graphia:annotation:a1> a oa:Annotation ;
    gfen:validationStatus gfen:validated ;
    gfen:validationMethod gfen:QuadraticVoting ;
    gfen:governanceDecisionId <https://w3id.org/fen/id/decision/g00042> ;
    gfen:reputationSnapshot <https://w3id.org/fen/id/reputation-snapshot/r00042> ;
    gfen:ledgerAnchor "0xA1B2C3" .
"""
INVALID_ANNOTATION = f"""
@prefix gfen: <{GFEN}> .
@prefix oa: <http://www.w3.org/ns/oa#> .

<urn:graphia:annotation:a2> a oa:Annotation ;
    gfen:validationStatus gfen:validated .   # missing governanceDecisionId
"""


def validate_data(data: str, data_format: str = "turtle") -> tuple:
    """(conforms, results_text) for ``data`` against the FEN shapes.

    The gfen: ontology is merged into the data graph: ``sh:class`` checks
    (e.g. ``gfen:validationStatus sh:class gfen:ValidationStatus``) rely on
    the class/individual declarations that live in the ontology, not in the
    written data itself.
    """
    ontology = ONTOLOGY_PATH.read_text(encoding="utf-8-sig")
    conforms, _, results_text = validate(
        ontology + "\n" + data, shacl_graph=str(SHAPES_PATH), data_graph_format=data_format
    )
    return bool(conforms), results_text


def self_check() -> int:
    ok_valid, text_valid = validate_data(VALID_ANNOTATION)
    if not ok_valid:
        print(f"FAIL: valid sample reported non-conforming:\n{text_valid}")
        return 1
    ok_invalid, text_invalid = validate_data(INVALID_ANNOTATION)
    if ok_invalid:
        print("FAIL: invalid sample (missing governanceDecisionId) reported conforming")
        return 1
    print(f"self-check OK (valid sample conforms; invalid sample rejected: {len(text_invalid.splitlines())} lines)")
    return 0


def check_graph_file(path: Path) -> int:
    data = path.read_text(encoding="utf-8")
    fmt = "trig" if path.suffix.lower() == ".trig" else "turtle"
    conforms, text = validate_data(data, fmt)
    print(f"{path}: {'conforms' if conforms else 'VIOLATIONS'}")
    if not conforms:
        print(text)
    return 0 if conforms else 1


def check_live(endpoint: str, graph: str) -> int:
    query = f"CONSTRUCT {{ ?s ?p ?o }} WHERE {{ GRAPH <{graph}> {{ ?s ?p ?o }} }}"
    resp = requests.post(
        endpoint, data={"query": query}, headers={"Accept": "text/turtle"}, timeout=15.0
    )
    resp.raise_for_status()
    conforms, text = validate_data(resp.text)
    print(f"graph {graph}: {'conforms' if conforms else 'VIOLATIONS'}")
    if not conforms:
        print(text)
    return 0 if conforms else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-file", type=Path)
    parser.add_argument("--endpoint", help="SPARQL query endpoint for the live check")
    parser.add_argument("--graph", help="named graph URI for the live check")
    args = parser.parse_args()
    if args.graph_file:
        return check_graph_file(args.graph_file)
    if args.endpoint:
        if not args.graph:
            parser.error("--endpoint requires --graph")
        return check_live(args.endpoint, args.graph)
    return self_check()


if __name__ == "__main__":
    sys.exit(main())
