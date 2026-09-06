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


class DelegationError(Exception):
    """Rejected delegation with the HTTP status the caller should return.

    Structured result (TECH-DEBT P2 config hygiene): the HTTP layer must not
    derive status codes by substring-matching error prose.
    """

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def apply_delegation(
    record: Optional[dict], voter: str, delegate: str, voting_mode: str
) -> None:
    """Register ``voter -> delegate`` on one proposal's record.

    Raises ``DelegationError`` (carrying the HTTP status code) on rejection;
    mutates ``record`` in place when accepted. Never returns a value.
    """
    if not voter or not delegate:
        raise DelegationError(422, "voter and delegate are required")
    if voter == delegate:
        raise DelegationError(422, "cannot delegate to yourself")
    if record is None:
        raise DelegationError(404, "unknown annotation_id")
    if record["status"] != "pending":
        raise DelegationError(409, f"candidate already decided: {record['status']}")
    if voting_mode != "qv":
        raise DelegationError(409, "delegation is a QV-mode feature (FEN_MOCK_VOTING=qv)")
    if voter in {v.get("voter") for v in record["qv_votes"]}:
        raise DelegationError(409, f"voter {voter} has already voted — no delegation")
    record["delegations"][voter] = delegate