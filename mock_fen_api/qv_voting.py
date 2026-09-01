"""Pure Quadratic Voting math for the mock DAO.

Demo stand-in only — the real Quadratic Voting system lives entirely outside
this repository (ADR-002); this module implements the same rules so the
contract in web/api.md can be exercised locally. Kept dependency-free (no
FastAPI, no state, no I/O) so the rules read as a spec and are unit-testable
in isolation (ADR-005: intensity cost curve, threshold, delegation weights).

The cost curve is capture-resistance, NOT the participation driver — see
ADR-005 and the motivation-stack decision (reputation capital + intrinsic
motivation; gamification is UX-only).
"""
from __future__ import annotations

from typing import Dict, Optional

OUTCOMES = ("validated", "disputed", "rejected")
MAX_INTENSITY = 5  # QV intensity cap (cost = i^2)


def majority_outcome(votes: Dict[str, int]) -> str:
    """Deterministic majority: highest count, ties broken by OUTCOMES order."""
    return max(OUTCOMES, key=lambda o: (votes.get(o, 0), -OUTCOMES.index(o)))


def quorum_total(votes: Dict[str, int]) -> int:
    return sum(votes.values())


def qv_cost(intensity: int) -> int:
    """Quadratic cost: a vote with weight ``intensity`` spends intensity^2
    credits (capture-resistance; the cost curve is not the participation
    driver — ADR-005)."""
    return intensity * intensity


def qv_scores(qv_votes: list, delegations: Optional[Dict[str, str]] = None) -> Dict[str, int]:
    """Weighted scores per outcome from QV votes (each vote carries an
    ``intensity`` weight). One voter may vote at most once per proposal —
    enforced in cast_vote (ADR-005 distinct-identity hint); scores weigh by
    intensity.

    Liquid democracy (ADR-005 decision 2): a voter who has NOT voted on the
    proposal but has delegated to a voter who did contributes one extra
    weight to the delegate's chosen outcome."""
    scores = {o: 0 for o in OUTCOMES}
    voted = set()
    for vote in qv_votes:
        voted.add(vote.get("voter"))
        scores[vote["outcome"]] += int(vote.get("intensity", 1))
    if delegations:
        for voter, delegate in delegations.items():
            if voter in voted or voter == delegate:
                continue
            for vote in qv_votes:
                if vote.get("voter") == delegate:
                    scores[vote["outcome"]] += 1
                    break
    return scores


def qv_decide(scores: Dict[str, int], threshold: int) -> Optional[str]:
    """Outcome whose weighted score reached the threshold; ties broken by
    OUTCOMES order. Returns None while the proposal is still open."""
    best = max(OUTCOMES, key=lambda o: (scores[o], -OUTCOMES.index(o)))
    return best if scores[best] >= threshold else None