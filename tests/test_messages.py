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
