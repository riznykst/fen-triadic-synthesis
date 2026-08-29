"""Python constants mirroring ``docs/ontology/fen-ontology.ttl`` — the additive
``gfen:`` namespace. Keep in sync with the .ttl file: if you change one, change
the other in the same commit (AGENT_PLAN.md, Phase 0, task 3).
"""
from __future__ import annotations

GFEN = "https://w3id.org/got/fen/ontology#"

# ---- Properties ---------------------------------------------------------
PROP_VALIDATION_STATUS = GFEN + "validationStatus"
PROP_VALIDATION_METHOD = GFEN + "validationMethod"
PROP_GOVERNANCE_DECISION_ID = GFEN + "governanceDecisionId"
PROP_REPUTATION_SNAPSHOT = GFEN + "reputationSnapshot"
PROP_LEDGER_ANCHOR = GFEN + "ledgerAnchor"
PROP_CONTRIBUTOR_PROFILE = GFEN + "contributorProfile"

# GovernanceDecision record properties (ADR-003, PID scheme)
PROP_APPLIES_TO = GFEN + "appliesTo"
PROP_QUORUM_REACHED = GFEN + "quorumReached"
PROP_OUTCOME = GFEN + "outcome"
PROP_DECIDED_AT = GFEN + "decidedAt"
PROP_SCAFFOLDING_SESSION = GFEN + "scaffoldingSession"

# ---- ValidationStatus individuals --------------------------------------
PENDING = GFEN + "pending"
VALIDATED = GFEN + "validated"
DISPUTED = GFEN + "disputed"
REJECTED = GFEN + "rejected"

# ---- ValidationMethod individuals ---------------------------------------
QUADRATIC_VOTING = GFEN + "QuadraticVoting"
PEER_REVIEW = GFEN + "PeerReview"

STATUS_MAP = {
    "pending": PENDING,
    "validated": VALIDATED,
    "disputed": DISPUTED,
    "rejected": REJECTED,
}

METHOD_MAP = {
    "quadratic_voting": QUADRATIC_VOTING,
    "peer_review": PEER_REVIEW,
}

# owl:imports stub — mirror of docs/ontology/fen-ontology.ttl. The additive
# gfen: namespace builds on GRAPHIA's TRIPLE Ontology (D2.2 section 3).
# TODO: replace with the official GRAPHIA Ontology IRI once confirmed
# (whitepaper section 7). Keep in sync with the .ttl file.
GRAPHIA_ONTOLOGY_IRI = "https://w3id.org/gotriple/ontology"
OWL_IMPORTS = GRAPHIA_ONTOLOGY_IRI