"""Env-driven settings for the Validation Result Consumer."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class ValidationConsumerConfig:
    kafka_bootstrap_servers: str
    topic_governance_decisions: str
    topic_validated: str
    sparql_update_endpoint: str
    fen_naan: str

    @classmethod
    def from_env(cls) -> "ValidationConsumerConfig":
        return cls(
            kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            topic_governance_decisions=os.getenv("TOPIC_GOVERNANCE_DECISIONS", "fen.governance.decisions.v1"),
            topic_validated=os.getenv("TOPIC_VALIDATED", "dap.entities.validated.v1"),
            sparql_update_endpoint=os.getenv("SPARQL_UPDATE_ENDPOINT", "http://localhost:3030/fen/update"),
            fen_naan=os.getenv("FEN_NAAN", "99999"),
        )
