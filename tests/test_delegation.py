"""Direct unit tests for mock_fen_api.delegation.apply_delegation.

Previously exercised only indirectly through the HTTP endpoint in
test_qv_scaffold.py (TECH-DEBT P2 blind spot): every branch of the pure
validation function is covered here offline. Rejections raise
``DelegationError`` with the HTTP status code the caller must return —
the HTTP layer never substring-matches error prose (TECH-DEBT P2 config
hygiene).
"""
from __future__ import annotations

import pytest

from mock_fen_api.delegation import DelegationError, apply_delegation


def _record(qv_votes=None, status="pending", delegations=None) -> dict:
    return {
        "status": status,
        "qv_votes": qv_votes or [],
        "delegations": delegations if delegations is not None else {},
    }


def test_delegation_registers_voter_to_delegate():
    record = _record()
    apply_delegation(record, "v1", "d1", "qv")
    assert record["delegations"] == {"v1": "d1"}


def test_delegation_requires_both_names():
    record = _record()
    with pytest.raises(DelegationError) as ei:
        apply_delegation(record, "", "d1", "qv")
    assert ei.value.status_code == 422
    assert "required" in ei.value.message
    with pytest.raises(DelegationError):
        apply_delegation(record, "v1", "", "qv")
    assert record["delegations"] == {}


def test_delegation_rejects_self_delegation():
    record = _record()
    with pytest.raises(DelegationError) as ei:
        apply_delegation(record, "v1", "v1", "qv")
    assert ei.value.status_code == 422
    assert "yourself" in ei.value.message
    assert record["delegations"] == {}


def test_delegation_rejects_unknown_record_with_404():
    with pytest.raises(DelegationError) as ei:
        apply_delegation(None, "v1", "d1", "qv")
    assert ei.value.status_code == 404
    assert ei.value.message == "unknown annotation_id"


def test_delegation_rejects_decided_candidate():
    record = _record(status="validated")
    with pytest.raises(DelegationError) as ei:
        apply_delegation(record, "v1", "d1", "qv")
    assert ei.value.status_code == 409
    assert "already decided" in ei.value.message
    assert record["delegations"] == {}


def test_delegation_is_qv_mode_only():
    record = _record()
    with pytest.raises(DelegationError) as ei:
        apply_delegation(record, "v1", "d1", "community")
    assert ei.value.status_code == 409
    assert "QV-mode" in ei.value.message
    assert record["delegations"] == {}


def test_delegation_rejected_after_voting():
    record = _record(qv_votes=[{"voter": "v1", "outcome": "validated", "intensity": 3}])
    with pytest.raises(DelegationError) as ei:
        apply_delegation(record, "v1", "d1", "qv")
    assert ei.value.status_code == 409
    assert "already voted" in ei.value.message
    assert record["delegations"] == {}


def test_redelgation_replaces_previous_delegate():
    record = _record(delegations={"v1": "d1"})
    apply_delegation(record, "v1", "d2", "qv")
    assert record["delegations"] == {"v1": "d2"}
