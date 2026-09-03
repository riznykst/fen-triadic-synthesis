"""Direct unit tests for mock_fen_api.delegation.apply_delegation.

Previously exercised only indirectly through the HTTP endpoint in
test_qv_scaffold.py (TECH-DEBT P2 blind spot): every branch of the pure
validation function is covered here offline.
"""
from __future__ import annotations

from mock_fen_api.delegation import apply_delegation


def _record(qv_votes=None, status="pending", delegations=None) -> dict:
    return {
        "status": status,
        "qv_votes": qv_votes or [],
        "delegations": delegations if delegations is not None else {},
    }


def test_delegation_registers_voter_to_delegate():
    record = _record()
    assert apply_delegation(record, "v1", "d1", "qv") is None
    assert record["delegations"] == {"v1": "d1"}


def test_delegation_requires_both_names():
    record = _record()
    assert "required" in apply_delegation(record, "", "d1", "qv")
    assert "required" in apply_delegation(record, "v1", "", "qv")
    assert record["delegations"] == {}


def test_delegation_rejects_self_delegation():
    record = _record()
    assert "yourself" in apply_delegation(record, "v1", "v1", "qv")
    assert record["delegations"] == {}


def test_delegation_rejects_unknown_record():
    assert apply_delegation(None, "v1", "d1", "qv") == "unknown annotation_id"


def test_delegation_rejects_decided_candidate():
    record = _record(status="validated")
    assert "already decided" in apply_delegation(record, "v1", "d1", "qv")
    assert record["delegations"] == {}


def test_delegation_is_qv_mode_only():
    record = _record()
    assert "QV-mode" in apply_delegation(record, "v1", "d1", "community")
    assert record["delegations"] == {}


def test_delegation_rejected_after_voting():
    record = _record(qv_votes=[{"voter": "v1", "outcome": "validated", "intensity": 3}])
    assert "already voted" in apply_delegation(record, "v1", "d1", "qv")
    assert record["delegations"] == {}


def test_redelgation_replaces_previous_delegate():
    record = _record(delegations={"v1": "d1"})
    assert apply_delegation(record, "v1", "d2", "qv") is None
    assert record["delegations"] == {"v1": "d2"}
