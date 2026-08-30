"""Agentic Scaffolding (Phase 1) — decision-support only (ADR-004).

Structures a natural-language statement into a semantic triple with schema
hints, relationships and ambiguity flags. Three cooperating agents:

1. Extractor — the LLM (OpenAI-compatible, FEN_LLM_*; any provider) or a
   deterministic rule fallback when no LLM is configured (offline demo).
2. Ontology Matcher — looks the triple's subject/object up in the mock's
   in-memory registry (stand-in for a SPARQL lookup against the existing
   knowledge graph).
3. Disambiguator — proposes external identifiers (Wikidata/GeoNames/…)
   via the LLM when configured; empty list otherwise.

The scaffolded triple is SHACL-validated against gfen:ScaffoldedTripleShape
(docs/ontology/fen-shapes.ttl) BEFORE it goes to voting; violations are data,
not errors (the UI shows them to the contributor).

Generic — works for ANY dataset type, not just linguistic entities. Real
scaffolding lives outside this repo (ADR-002); this is the demo
implementation of the same contract.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF

from services.common import gfen_ontology as ns
from services.common.llm import chat_completion

logger = logging.getLogger(__name__)

_SCAFFOLD_SYSTEM = (
    "You are an Agentic Scaffolding layer for a community data-governance "
    "framework (validation overlay for ANY dataset type). Analyse the statement "
    "and return ONLY this JSON (no markdown, no code fences): "
    '{"schema_hints": ["2-3 brief schema guidance notes for structuring this knowledge"], '
    '"relationships": ["1-3 semantic relationships identified in the text"], '
    '"ambiguities": ["any ambiguity or missing context - empty array [] if none"], '
    '"triple": {"subject": "...", "predicate": "...", "object": "...", "context": "...", '
    '"language_or_domain": "...", "evidence_type": "personal_expertise | community_consensus | archival"}}'
)


def parse_scaffold_json(answer: Optional[str]) -> Optional[dict]:
    """Parse the scaffold agent's JSON answer; tolerate code fences."""
    if not answer:
        return None
    try:
        cleaned = answer.replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned)
        triple = data.get("triple")
        if not isinstance(triple, dict) or not triple.get("subject"):
            return None
        return {
            "schema_hints": data.get("schema_hints", []),
            "relationships": data.get("relationships", []),
            "ambiguities": data.get("ambiguities", []),
            "triple": triple,
            "source": "llm",
        }
    except (json.JSONDecodeError, TypeError):
        return None


def ontology_match(triple: dict, registry: list) -> list:
    """Agent 2 — Ontology Matcher (demo): look the triple's subject/object up
    in the mock's in-memory registry (stand-in for a SPARQL lookup against
    the existing knowledge graph). Returns known candidates with matching
    labels."""
    labels = {str(triple.get("subject", "")).lower(), str(triple.get("object", "")).lower()}
    matches = []
    for rec in registry:
        label = str(rec.get("entity_label") or "").lower()
        if label and label in labels:
            matches.append({
                "annotation_id": rec["annotation_id"],
                "entity_label": rec.get("entity_label"),
                "status": rec.get("status"),
            })
    return matches


def disambiguate(triple: dict, llm_config) -> list:
    """Agent 3 — Disambiguator: propose external identifiers. Uses the LLM
    (decision-support, ADR-004) when configured; otherwise returns an empty
    list (the demo keeps working offline)."""
    if not llm_config.enabled:
        return []
    answer = chat_completion(
        llm_config,
        "You are a knowledge-graph disambiguator. For the given triple, reply "
        "with a JSON array of external identifiers, each "
        '{"type": "wikidata"|"geonames"|"getty", "value": "<id>", "label": "<short label>"}. '
        "Reply with [] if nothing applies. JSON only.",
        json.dumps(triple, ensure_ascii=False),
    )
    if not answer:
        return []
    try:
        parsed = json.loads(answer)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)][:5]
    except json.JSONDecodeError:
        logger.warning("disambiguator returned non-JSON; ignoring")
    return []


def shacl_validate_scaffold(triple: dict) -> dict:
    """Validate a scaffolded triple against gfen:ScaffoldedTripleShape
    (docs/ontology/fen-shapes.ttl) BEFORE it goes to voting. Returns
    ``{valid, violations}``. Never raises — validation failures are data,
    not errors (the UI shows them to the contributor). Falls back to
    ``valid: None`` when pyshacl is unavailable."""
    try:
        from pyshacl import validate  # lazy: pyshacl is a demo-time dependency

        graph = Graph()
        node = URIRef("urn:fen:scaffold:triple")
        graph.add((node, RDF.type, URIRef(ns.SCAFFOLDED_TRIPLE)))
        for field, prop_uri in (
            ("subject", ns.PROP_SUBJECT),
            ("predicate", ns.PROP_PREDICATE),
            ("object", ns.PROP_OBJECT),
            ("language_or_domain", ns.PROP_LANGUAGE_OR_DOMAIN),
        ):
            value = triple.get(field)
            if value:
                graph.add((node, URIRef(prop_uri), Literal(str(value))))
        shapes_path = Path(__file__).resolve().parents[1] / "docs" / "ontology" / "fen-shapes.ttl"
        conforms, results_graph, _ = validate(graph, shacl_graph=str(shapes_path))
        violations = []
        if not conforms:
            for _s, pred, obj in results_graph:
                if str(pred).endswith("resultMessage"):
                    violations.append(str(obj))
        return {"valid": bool(conforms), "violations": violations[:5]}
    except Exception as exc:  # noqa: BLE001 - validation is advisory in the demo
        logger.warning("SHACL validation unavailable (%s)", exc)
        return {"valid": None, "violations": [], "error": str(exc)}


def run_scaffold(text: str, llm_config, registry: list) -> dict:
    """Full Scaffold pipeline for one statement: LLM extract (or rule
    fallback) -> SHACL check -> matcher/disambiguator agents.

    ``registry`` is a list of candidate records (the mock's in-memory store)
    used by the Ontology Matcher. Returns the scaffold response dict."""
    if llm_config.enabled:
        answer = chat_completion(llm_config, _SCAFFOLD_SYSTEM, text)
        parsed = parse_scaffold_json(answer)
        if parsed:
            parsed["shacl"] = shacl_validate_scaffold(parsed.get("triple", {}))
            parsed["agents"] = {
                "extractor": "llm",
                "matcher": ontology_match(parsed.get("triple", {}), registry),
                "disambiguator": disambiguate(parsed.get("triple", {}), llm_config),
            }
            return parsed
        logger.warning("scaffold agent unavailable/indecisive; using rule fallback")

    snippet = text[:48]
    response = {
        "schema_hints": ["rule-based fallback (no LLM configured) — the triple is a rough split"],
        "relationships": [],
        "ambiguities": [],
        "triple": {
            "subject": snippet,
            "predicate": "mentions",
            "object": text[-48:] if len(text) > 96 else snippet,
            "context": "",
            "language_or_domain": "und",
            "evidence_type": "community_consensus",
        },
        "source": "rule_fallback",
    }
    response["shacl"] = shacl_validate_scaffold(response["triple"])
    response["agents"] = {
        "extractor": "rule",
        "matcher": ontology_match(response["triple"], registry),
        "disambiguator": [],
    }
    return response