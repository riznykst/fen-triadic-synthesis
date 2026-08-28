"""Shared Kafka message contracts — the single source of truth for the
shapes of the three message types used across the FEN pipeline.

JSON Schemas in ``schemas/kafka-events/`` are GENERATED from these models
(see ``scripts/generate_schemas.py``) — never hand-edit the generated files.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ValidationStatus(str, Enum):
    """Governance status of a candidate entity (mirrors gfen:ValidationStatus)."""

    pending = "pending"
    validated = "validated"
    disputed = "disputed"
    rejected = "rejected"


class ValidationMethod(str, Enum):
    """Validation method used by the community (mirrors gfen:ValidationMethod)."""

    quadratic_voting = "quadratic_voting"
    peer_review = "peer_review"


class EntityCandidate(BaseModel):
    """A candidate entity emitted by the WP4 extraction pipeline (status=pending)."""

    model_config = ConfigDict(extra="ignore")

    annotation_id: str = Field(description="Identifier of the oa:Annotation created by WP4 extraction")
    document_id: Optional[str] = Field(default=None, description="Identifier of the source triple:Document")
    entity_label: Optional[str] = Field(default=None, description="Human-readable label of the extracted entity")
    entity_type: Optional[str] = Field(default=None, description="Extracted type, e.g. schema:Person")
    extracted_by: str = Field(default="wp4_entity_extractor", description="Service that produced the candidate")
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GovernanceDecision(BaseModel):
    """A DAO governance decision returned by the FEN system via webhook."""

    model_config = ConfigDict(extra="ignore")

    annotation_id: str = Field(description="Identifier of the oa:Annotation the decision applies to")
    document_id: Optional[str] = Field(default=None, description="Identifier of the source triple:Document")
    decision_id: str = Field(description='FEN decision id, e.g. "g00042" (ark:{NAAN}/g#####)')
    outcome: ValidationStatus = Field(description="validated | disputed | rejected")
    method: ValidationMethod = Field(description="quadratic_voting | peer_review")
    quorum_reached: bool = Field(default=False, description="Whether the DAO quorum was reached")
    reputation_snapshot_id: str = Field(description='Reputation snapshot id, e.g. "r00042"')
    ledger_anchor: Optional[str] = Field(default=None, description="On-chain tx hash — anchor only, never content")
    decided_at: datetime = Field(description="Decision timestamp (UTC)")


class EntityValidated(BaseModel):
    """Confirmation published to dap.entities.validated.v1 once the SPARQL update lands."""

    model_config = ConfigDict(extra="ignore")

    annotation_id: str
    document_id: Optional[str] = None
    decision_id: str
    outcome: ValidationStatus
    validated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
