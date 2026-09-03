"""Tests for the shared Pydantic message contracts."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.common.messages import (
    EntityCandidate,
    EntityValidated,
    GovernanceDecision,
    ValidationMethod,
    ValidationStatus,
)


def _decision_payload(**overrides) -> dict:
    base = dict(
        annotation_id="annotation_a1",
        document_id="d12345",
        decision_id="g00042",
        outcome="validated",
        method="quadratic_voting",
        quorum_reached=True,
        reputation_snapshot_id="r00042",
        ledger_anchor="0xA1B2C3",
        decided_at="2026-08-25T10:14:00Z",
    )
    base.update(overrides)
    return base


def test_governance_decision_parses_and_coerces():
    d = GovernanceDecision.model_validate(_decision_payload())
    assert d.outcome is ValidationStatus.validated
    assert d.method is ValidationMethod.quadratic_voting
    assert d.decided_at.isoformat().startswith("2026-08-25T10:14:00")


def test_governance_decision_rejects_unknown_outcome():
    with pytest.raises(ValidationError):
        GovernanceDecision.model_validate(_decision_payload(outcome="bogus"))


def test_governance_decision_roundtrip():
    d = GovernanceDecision.model_validate(_decision_payload())
    assert GovernanceDecision.model_validate(d.model_dump()) == d


def test_entity_candidate_roundtrip():
    c = EntityCandidate(annotation_id="annotation_a1", entity_label="Ada Lovelace")
    assert EntityCandidate.model_validate(c.model_dump()) == c
    assert c.extracted_by == "wp4_entity_extractor"


def test_entity_candidate_requires_annotation_id():
    with pytest.raises(ValidationError):
        EntityCandidate()


def test_entity_validated_roundtrip():
    v = EntityValidated(annotation_id="annotation_a1", decision_id="g00042", outcome="validated")
    assert v.outcome is ValidationStatus.validated
    assert EntityValidated.model_validate(v.model_dump()) == v


def test_json_schemas_generate_for_all_models():
    for model in (EntityCandidate, GovernanceDecision, EntityValidated):
        schema = model.model_json_schema()
        assert "properties" in schema
        assert schema["type"] == "object"


def test_committed_kafka_schemas_match_models():
    """TECH-DEBT P1: schemas/kafka-events/*.schema.json are generated from
    the Pydantic models (scripts/generate_schemas.py). A field added or
    renamed in messages.py must never silently leave the published schemas
    stale — regenerate in memory and compare with the committed files."""
    import json
    from pathlib import Path

    out_dir = Path(__file__).resolve().parents[1] / "schemas" / "kafka-events"
    expected = {
        "entity-candidate": EntityCandidate,
        "governance-decision": GovernanceDecision,
        "entity-validated": EntityValidated,
    }
    for name, model in expected.items():
        path = out_dir / f"{name}.schema.json"
        assert path.exists(), f"missing committed schema {path}"
        committed = json.loads(path.read_text(encoding="utf-8"))
        fresh = model.model_json_schema()
        assert committed == fresh, (
            f"schemas/kafka-events/{name}.schema.json is STALE — "
            "run `python scripts/generate_schemas.py` and commit the result"
        )
