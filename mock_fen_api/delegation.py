"""Liquid-democracy delegation (ADR-005 decision 2) for the mock DAO.

Pure record mutation + validation, no I/O, no FastAPI: a voter who has NOT
voted on a proposal yet can delegate their weight to another voter; delegated
weight follows the delegate's outcome choice in qv_scores (qv_voting.py).
One active delegation per voter per proposal (re-delegation replaces it).

Real identity/delegation mechanics live outside this repo (ADR-002); this is
the demo implementation of the same contract.
"""
from __future__ import annotations

from typing import Optional


def apply_delegation(
    record: Optional[dict], voter: str, delegate: str, voting_mode: str
) -> Optional[str]:
    """Register ``voter -> delegate`` on one proposal's record.

    Returns ``None`` on success, or an error message describing the rejected
    delegation (caller maps it to an HTTP status). Mutates ``record`` in
    place when accepted.
    """
    if not voter or not delegate:
        return "voter and delegate are required"
    if voter == delegate:
        return "cannot delegate to yourself"
    if record is None:
        return "unknown annotation_id"
    if record["status"] != "pending":
        return f"candidate already decided: {record['status']}"
    if voting_mode != "qv":
        return "delegation is a QV-mode feature (FEN_MOCK_VOTING=qv)"
    if voter in {v.get("voter") for v in record["qv_votes"]}:
        return f"voter {voter} has already voted — no delegation"
    record["delegations"][voter] = delegate
    return None